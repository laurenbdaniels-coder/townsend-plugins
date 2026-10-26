#!/usr/bin/env python3
"""Plan the helpers' slices for a full read (custody-check 0.7.0, S-068).

Run from the folder that contains the app: full_read_slices.py --repo <app>
Prints one JSON line: {"ok", "slices": [{"n", "paths"}], "excluded", "stopped_at_cap", "eligible"}.
Eligible = inventory code files + operational files (allowlist), minus every file helper_read_guard.never_open
refuses and every file the scanner flagged for Q1 (whole-file exclusion). Slices: by folder, <=40 files,
<=6,000 lines (unknown = 6,000), at most 8; server/handler/ops files first.
"""
import argparse, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN = os.path.join(HERE, "custody_scan.py")
_guard = {"__name__": "helper_read_guard", "__file__": os.path.join(HERE, "helper_read_guard.py")}
with open(os.path.join(HERE, "helper_read_guard.py"), encoding="utf-8") as _fh:
    exec(compile(_fh.read(), "helper_read_guard.py", "exec"), _guard)
never_open = _guard["never_open"]
SKIP_DIRS = _guard["NEVER_DIRS"]
OPS = re.compile(r"^(vercel\.json|netlify\.toml|fly(\.[\w-]+)?\.toml|render\.yaml|railway\.json|app\.json|wrangler\.toml|"
                 r"supabase/config\.toml|\.github/workflows/[^/]+\.ya?ml|\.github/CODEOWNERS|CODEOWNERS|docs/CODEOWNERS|"
                 r"\.github/pull_request_template\.md|\.github/PULL_REQUEST_TEMPLATE/[^/]+\.md|Dockerfile|Procfile|"
                 r"sentry\.[\w.-]+\.config\.\w+|instrumentation(-client)?\.\w+|package\.json|pyproject\.toml|requirements\.txt|"
                 r"nixpacks\.toml|scripts/[^/]+\.(sh|mjs|js|ts|py)|supabase/migrations/[^/]+\.sql|prisma/schema\.prisma|"
                 r"\.coderabbit\.ya?ml|promptfooconfig\.ya?ml)$")
MAX_FILES, MAX_LINES, MAX_SLICES = 40, 6000, 8


def jline(out):
    return json.loads(next((l for l in out.splitlines() if l.startswith("{")), "{}"))


def count_lines(p):
    try:
        with open(p, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return MAX_LINES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    a = ap.parse_args()
    root = os.path.abspath(a.repo)
    if os.path.islink(a.repo) or not os.path.isdir(root):
        print(json.dumps({"ok": False, "error": "repo-not-found"}))
        return
    scan = jline(subprocess.run([sys.executable, SCAN, "--repo", a.repo], capture_output=True, text=True, timeout=600).stdout)
    inv = jline(subprocess.run([sys.executable, SCAN, "--repo", a.repo, "--inventory"], capture_output=True, text=True, timeout=600).stdout)
    if not scan.get("ok") or not inv.get("ok"):
        print(json.dumps({"ok": False, "error": "scan-or-inventory-failed"}))
        return
    q1 = (scan.get("questions") or {}).get("q1") or {}
    flagged = {e.get("path") for e in q1.get("evidence", []) if e.get("path")}
    if scan.get("partial") or (scan.get("stats") or {}).get("q1_rows_capped"):
        print(json.dumps({"ok": True, "slices": [], "excluded": len(flagged), "stopped_at_cap": "scan-partial-or-capped", "eligible": 0}))
        return
    rows = {}
    for r in inv.get("files", []):
        path, lines = r[0], r[1]
        pri = 0 if (len(r) > 3 and (r[2] or r[3])) else 2
        rows[path] = (lines or MAX_LINES, pri)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not os.path.islink(os.path.join(dp, d))]
        for f in fns:
            rel = os.path.relpath(os.path.join(dp, f), root)
            if OPS.match(rel) and rel not in rows and not os.path.islink(os.path.join(dp, f)):
                rows[rel] = (count_lines(os.path.join(dp, f)), 1)
    excluded = 0
    elig = []
    for rel, (lines, pri) in rows.items():
        if rel in flagged or never_open(rel.split("/")):
            excluded += 1
            continue
        elig.append((pri, rel, lines))
    elig.sort(key=lambda t: (t[0], t[1]))
    # group by folder within priority order, then pack
    slices, cur, cur_lines = [], [], 0
    left = []
    by_folder = {}
    order = []
    for pri, rel, lines in elig:
        k = (pri, os.path.dirname(rel))
        if k not in by_folder:
            by_folder[k] = []
            order.append(k)
        by_folder[k].append((rel, lines))
    for k in order:
        for rel, lines in by_folder[k]:
            lines = min(lines, MAX_LINES)
            if cur and (len(cur) >= MAX_FILES or cur_lines + lines > MAX_LINES):
                slices.append(cur)
                cur, cur_lines = [], 0
            if len(slices) >= MAX_SLICES:
                left.append(rel)
                continue
            cur.append(rel)
            cur_lines += lines
    if cur and len(slices) < MAX_SLICES:
        slices.append(cur)
    elif cur:
        left += cur
    print(json.dumps({"ok": True, "slices": [{"n": i + 1, "paths": s} for i, s in enumerate(slices)],
                      "excluded": excluded, "stopped_at_cap": len(left), "eligible": len(elig)}))


if __name__ == "__main__":
    main()
