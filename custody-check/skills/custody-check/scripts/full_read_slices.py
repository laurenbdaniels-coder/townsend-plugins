#!/usr/bin/env python3
"""Plan the helpers' slices for a full read (custody-check 0.7.0, S-068).

Run from the folder that contains the app, with the same extra flags the scanner got:
  full_read_slices.py --repo <app> [--exclude-dir D ...] [--browser-prefix P ...] [--max-files N] [--max-file-bytes N]
Prints one JSON line: {"ok", "slices": [{"n", "paths"}], "excluded", "stopped_at_cap", "eligible"}, or
{"ok": false, "error": <code>}. No file is ever listed that:
  - helper_read_guard.never_open refuses (env, key, credential, instruction, lock and build files),
  - the scanner flagged for a key (compared by the scanner's own masked path, so long names still match),
  - the scanner did not check for keys (settings files) and that holds a key shape by the scanner's patterns,
  - sits under a folder the founder excluded.
It refuses (no helpers) when the scan is partial, the key check did not finish, or the key list is full.
Slices: by folder, <=40 files, <=6,000 lines (unknown = 6,000), at most 8; server/handler/settings files first.
"""
import argparse, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "custody_scan.py")


def _load(name):
    ns = {"__name__": name, "__file__": os.path.join(HERE, name + ".py")}
    with open(ns["__file__"], encoding="utf-8") as fh:
        exec(compile(fh.read(), ns["__file__"], "exec"), ns)
    return ns


_guard = _load("helper_read_guard")
_guard["load_shared"]()
never_open = _guard["never_open"]
SKIP_DIRS = _guard["NEVER_DIRS"]
_scan = _load("custody_scan")
release = _scan["release"]  # the frozen 0.3.2 scanner, loaded and hash-checked as the scan does
# File types the scanner reads for keys (measured 2026-10-26: code, and .json/.toml/.yaml settings except package.json).
# Every other listed file gets the key-shape check below before a helper may read it.
KEY_CHECKED_EXTS = set(release.CODE_EXTS) | set(_scan["MODULE_EXTS"]) | {".json", ".toml", ".yaml", ".yml"}
NOT_KEY_CHECKED = {"package.json"}
OPS = re.compile(r"^(vercel\.json|netlify\.toml|fly(\.[\w-]+)?\.toml|render\.yaml|railway\.json|app\.json|wrangler\.toml|"
                 r"supabase/config\.toml|\.github/workflows/[^/]+\.ya?ml|\.github/CODEOWNERS|CODEOWNERS|docs/CODEOWNERS|"
                 r"\.github/pull_request_template\.md|\.github/PULL_REQUEST_TEMPLATE/[^/]+\.md|Dockerfile|Procfile|"
                 r"sentry\.[\w.-]+\.config\.\w+|instrumentation(-client)?\.\w+|package\.json|pyproject\.toml|requirements\.txt|"
                 r"nixpacks\.toml|scripts/[^/]+\.(sh|mjs|js|ts|py)|supabase/migrations/[^/]+\.sql|prisma/schema\.prisma|"
                 r"\.coderabbit\.ya?ml|promptfooconfig\.ya?ml)$")
MAX_FILES, MAX_LINES, MAX_SLICES = 40, 6000, 8
MAX_Q1_ROWS = release.MAX_EVIDENCE  # at this many Q1 rows the key list may be cut short
KEY_SHAPES = (release.NAMED_KEY_RE, release.PRIVATE_KEY_RE, release.JWT_RE, release.GENERIC_TOKEN_RE)
MAX_CHECK_BYTES = 512 * 1024


def out(obj):
    print(json.dumps(obj))


def jline(text):
    return json.loads(next((l for l in text.splitlines() if l.startswith("{")), "{}"))


def scanner(args):
    return jline(subprocess.run([sys.executable, "-I", SCAN] + args, capture_output=True, text=True, timeout=900).stdout)


def holds_key_shape(path):
    """True when a file the scanner never checks for keys holds anything key-shaped, or cannot be checked."""
    try:
        if os.path.getsize(path) > MAX_CHECK_BYTES:
            return True
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return True
    return any(rx.search(text) for rx in KEY_SHAPES)


def key_checked(rel):
    name = rel.rsplit("/", 1)[-1]
    return os.path.splitext(name)[1].lower() in KEY_CHECKED_EXTS and name not in NOT_KEY_CHECKED


def count_lines(p):
    try:
        with open(p, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return MAX_LINES


def plan(a):
    root = os.path.abspath(a.repo)
    if os.path.islink(a.repo) or not os.path.isdir(root):
        return {"ok": False, "error": "repo-not-found"}
    flags = []
    for d in a.exclude_dir:
        flags += ["--exclude-dir", d]
    for p in a.browser_prefix:
        flags += ["--browser-prefix", p]
    if a.max_files is not None:
        flags += ["--max-files", str(a.max_files)]
    if a.max_file_bytes is not None:
        flags += ["--max-file-bytes", str(a.max_file_bytes)]
    scan = scanner(["--repo", a.repo] + flags)
    if not scan.get("ok"):
        return {"ok": False, "error": "scan-failed"}
    q1 = (scan.get("questions") or {}).get("q1") or {}
    evidence = q1.get("evidence", [])
    if scan.get("partial"):
        return {"ok": False, "error": "scan-partial"}
    if (scan.get("stats") or {}).get("overlay_fallback") or any(e.get("check") == "checks-not-finished" for e in evidence):
        return {"ok": False, "error": "key-check-unfinished"}
    if len(evidence) >= MAX_Q1_ROWS:
        return {"ok": False, "error": "key-list-full"}
    flagged = {e.get("path") for e in evidence if e.get("path")}
    inv = scanner(["--repo", a.repo, "--inventory"] + flags)
    if not inv.get("ok"):
        return {"ok": False, "error": "inventory-failed"}
    excluded_dirs = {d.strip("/").replace("\\", "/") for d in a.exclude_dir}

    def in_excluded(rel):
        parts = rel.split("/")
        return any(d in parts[:-1] or rel.startswith(d + "/") for d in excluded_dirs)

    rows = {}  # rel -> (lines, priority, read for keys by the scanner)
    for r in inv.get("files", []):
        path, lines = r[0], r[1]
        pri = 0 if (len(r) > 3 and (r[2] or r[3])) else 2
        rows[path] = (MAX_LINES if lines is None else lines, pri, key_checked(path))
    unlisted = max(0, (inv.get("code_files") or 0) - len(inv.get("files", [])))
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not os.path.islink(os.path.join(dp, d))
                  and not in_excluded(os.path.relpath(os.path.join(dp, d), root).replace(os.sep, "/") + "/x")]
        for f in fns:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if OPS.match(rel) and rel not in rows and not os.path.islink(full):
                rows[rel] = (count_lines(full), 1, key_checked(rel))
    excluded, elig = 0, []
    for rel, (lines, pri, checked) in rows.items():
        if (rel in flagged or release.sanitize_path(rel) in flagged or never_open(rel.split("/")) or in_excluded(rel)
                or (not checked and holds_key_shape(os.path.join(root, rel)))):
            excluded += 1
            continue
        elig.append((pri, rel, lines))
    elig.sort(key=lambda t: (t[0], os.path.dirname(t[1]), t[1]))  # priority, then folder, then path
    slices, cur, cur_lines, left = [], [], 0, []
    for _pri, rel, lines in elig:
        lines = min(lines, MAX_LINES)
        if cur and (len(cur) >= MAX_FILES or cur_lines + lines > MAX_LINES):
            slices.append(cur)
            cur, cur_lines = [], 0
        if len(slices) >= MAX_SLICES:
            left.append(rel)
            continue
        cur.append(rel)
        cur_lines += lines
    if cur:
        slices.append(cur)
    return {"ok": True, "slices": [{"n": i + 1, "paths": s} for i, s in enumerate(slices)],
            "excluded": excluded, "stopped_at_cap": len(left) + unlisted, "eligible": len(elig)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--exclude-dir", action="append", default=[])
    ap.add_argument("--browser-prefix", action="append", default=[])
    ap.add_argument("--max-files", type=int)
    ap.add_argument("--max-file-bytes", type=int)
    try:
        a = ap.parse_args()
    except SystemExit:
        out({"ok": False, "error": "usage"})
        return
    try:
        out(plan(a))
    except Exception:  # any failure means no helpers, and the agent still gets its one line
        out({"ok": False, "error": "plan-failed"})


if __name__ == "__main__":
    main()
