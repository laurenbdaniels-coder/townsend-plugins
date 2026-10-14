#!/usr/bin/env python3
"""decision-census helper: lists candidate places where an app decides four things.

Read-only. Prints ONE JSON line. Nothing from inside a file ever reaches the output: every
string is a repo-relative path (only when it passes a strict character rule) or a member of
the fixed VOCABULARY below. The skill reads short windows around the listed lines itself.

Decision types: visibility (who can see a record), price (what something costs),
paid (whether someone has paid), rounding (how money rounds).
"""
__version__ = "0.1.0"

import sys

_DOCS = "README.md#when-it-goes-wrong"
HINTS = {
    "usage": "Pass the app folder with --repo. Run from the folder that contains your app: python3 census_scan.py --repo my-app",
    "repo-not-found": "The --repo folder was not found. Run from the folder that contains your app and pass its name.",
    "repo-not-a-directory": "The --repo path is a file, not a folder. Pass the app folder itself.",
    "repo-is-symlink": "The --repo path is a symbolic link. Pass the real folder (the link's target) instead.",
    "repo-unreadable": "The --repo folder cannot be read. Check its permissions or copy the app somewhere you own.",
    "repo-contains-cwd": "The folder you named is the folder you launched from, or contains it. Run from the folder that contains your app and pass its name, never . or ..",
    "python-too-old": "This helper needs python 3.9 or newer. Run python3 --version; on macOS install the Command Line Tools.",
    "internal": "The helper hit an unexpected error. Ask the four signs by hand and file an issue.",
}


def version_guard(version_info):
    """Return a failure envelope when the interpreter is too old, else None."""
    if tuple(version_info[:2]) < (3, 9):
        return {"ok": False, "error": "python-too-old", "hint": HINTS["python-too-old"], "partial": True}
    return None


_guard = version_guard(sys.version_info)
if _guard is not None and __name__ == "__main__":
    import json as _json
    sys.stdout.write(_json.dumps(_guard, separators=(",", ":")) + "\n")
    sys.exit(0)

import argparse
import json
import os
import re
import stat
import time


# ------------------------------------------------- walk rules (copied from custody-check 0.3.2)

EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "vendor", "venv", ".venv", "__pycache__", "coverage"}
NEVER_OPEN_DIRS = {".claude", ".codex", ".agents", ".windsurf", ".clinerules", ".gemini", ".kiro", ".roo", ".trae", ".augment", ".amazonq", ".junie", ".continue", ".aider", ".opencode"}
NEVER_OPEN_DIR_PAIRS = {(".cursor", "rules"), (".github", "instructions"), (".github", "prompts"), (".github", "agents")}
NEVER_OPEN_FILE_RE = re.compile(r"^(?:claude|agents?|gemini|conventions|copilot-instructions)(?:[.-][^/]*)?\.md$|^\.aider.*$|.*\.prompt\.md$|.*\.agent\.md$|.*\.instructions\.md$|.*\.mdc$", re.I)
NEVER_OPEN_FILES = {".cursorrules", ".windsurfrules", ".clinerules", ".rules", "opencode.json", ".roomodes"}
SKIP_BASENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "cargo.lock", "composer.lock", "gemfile.lock"}
SKIP_EXT_SUFFIXES = (".map", ".min.js", ".min.css", ".bundle.js")
CODE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".py", ".rb", ".go", ".java", ".kt", ".php", ".cs", ".swift", ".dart"}
SQL_EXTS = {".sql", ".psql", ".pgsql", ".ddl"}
SCHEMA_EXTS = {".prisma", ".graphql", ".gql"}
SCAN_EXTS = CODE_EXTS | SQL_EXTS | SCHEMA_EXTS
STOPLINE_FIELDS = {"ssn", "social_security", "dob", "date_of_birth", "birthdate", "medical", "diagnosis", "credit_card", "card_number", "cc_number", "iban", "passport"}
MAX_PATH_CHARS = 200
LINE_CLIP_CHARS = 2048
BINARY_SNIFF_BYTES = 8192
MAX_NEVER_OPEN_COUNT = 10000
MAX_DIR_ENTRIES = 50000

# ------------------------------------------------------------------ census rules

TYPES = ("visibility", "price", "paid", "rounding")
STRENGTHS = ("strong", "weak")
MAX_PER_FILE_PER_TYPE = 5
MAX_PER_TYPE = 40
MAX_STOPLINE_HINTS = 12
MAX_OUTPUT_BYTES = 30000
DEFAULT_MAX_FILES = 20000
DEFAULT_MAX_FILE_BYTES = 524288
DEFAULT_MAX_TOTAL_BYTES = 268435456
DEFAULT_DEADLINE_S = 120.0
SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._@+()\[\]-]+$")
TEST_FILE_RE = re.compile(r"[._-](?:test|spec)\.[A-Za-z0-9]+$", re.I)
TEST_DIRS = {"__tests__", "__mocks__", "tests", "test", "spec", "e2e", "cypress", "playwright"}
SCHEMA_NAME_RE = re.compile(r"schema|model|types|entities", re.I)

# Money words inside an identifier (unitPrice, PRO_PRICE, baseFee, subtotal, cents).
MONEY_RE = re.compile(r"price|amount|total|cost|fee|tax|discount|cents|charge|balance|payout|refund", re.I)
PRICE_CONST_IDENT_RE = re.compile(r"price|cost|fee|amount|tax", re.I)
IDENT = r"[A-Za-z_$][\w$]*"
DOTTED = r"[A-Za-z_$][\w$.]*"
# identifier, an arithmetic operator, an operand. "-" never starts "->" or "--"; "/" never starts a comment.
ARITH_RE = re.compile(r"(" + DOTTED + r")\s*(\*=?|/=?(?![/*])|\+=?(?!\+)|-=?(?![->]))\s*(" + DOTTED + r"|\d[\d_.]*|\()")
# "shippingCost = weight * 0.5": arithmetic assigned to a money-named target counts even when no operand is money.
ASSIGN_TARGET_RE = re.compile(r"(" + IDENT + r")\s*(?::[^=]{0,40})?(?<![=!<>])=(?![=>])")
ASSIGN_CONTEXT_RE = re.compile(r"(?<![=!<>])=(?![=>])|\breturn\b|\(")
COND_CONTEXT_RE = re.compile(r"\bif\b|&&|\|\||\?|\breturn\b|!\s*[\w$.]|\bwhile\b|\bfilter\b|\bwhere\b|\bunless\b|\bwhen\b")
STR_CHAR_RE = re.compile(r"[\"'`\\]")

# (pattern id, strength, compiled regex, source) where source is "code" (strings blanked) or "raw".
# A *_MONEY suffix in the id list below means the line must also hold a money word.
_I = re.I
PATTERNS = {
    "visibility": [
        ("role-compare", "strong", re.compile(r"\brole\w*\s*(?:===?|!==?)|(?:===?|!==?)\s*[\w$.]*\.role\b|\bhas_?role\s*\(", _I), "code"),
        ("owner-compare", "strong", re.compile(r"(?:owner_?id|user_?id|author_?id|created_?by|tenant_?id|org_?id|account_?id)\s*(?:===?|!==?)|(?:===?|!==?)\s*[\w$.]*(?:owner_?id|user_?id|author_?id|created_?by|tenant_?id|org_?id|account_?id)\b", _I), "code"),
        ("owner-filter", "strong", re.compile(r"\.eq\(\s*['\"](?:user_id|owner_id|author_id|tenant_id|org_id|account_id)['\"]|\bwhere\s*:\s*\{\s*(?:userId|ownerId|authorId|tenantId|orgId|user_id|owner_id)\b", _I), "raw"),
        ("row-policy", "strong", re.compile(r"\bcreate\s+policy\b|\bauth\.uid\s*\(\s*\)", _I), "raw"),
        ("access-check", "strong", re.compile(r"\b(?:can_?view|can_?access|can_?read|can_?see|can_?edit|can_?delete|has_?access|has_?permission|is_?allowed|authorize)\w*\s*\(", _I), "code"),
        ("visibility-compare", "strong", re.compile(r"\b(?:is_?public|is_?private|visibility|is_?published)\s*(?:===?|!==?)", _I), "code"),
        ("admin-check", "strong", re.compile(r"\b(?:is_?admin|is_?super_?admin|is_?superuser|is_?staff|is_?owner|is_?moderator)\b", _I), "code+cond"),
        ("admin-name", "weak", re.compile(r"\b(?:is_?admin|is_?super_?admin|is_?superuser|is_?staff|is_?owner|is_?moderator)\b", _I), "code"),
    ],
    "price": [
        ("price-arith", "strong", None, "arith"),
        ("price-compare", "strong", re.compile(r"(" + IDENT + r")\s*(?:[<>]=?)\s*\d"), "money-compare"),
        ("discount-rule", "strong", re.compile(r"\b\w*(?:discount|coupon|percent_?off)\w*\s*(?:[<>]=?|===?|!==?)", _I), "code"),
        ("price-constant", "weak", re.compile(r"(" + IDENT + r")\s*[:=](?!=)\s*-?\d[\d_.]*\b"), "price-const"),
        ("billing-price-id", "weak", re.compile(r"\b(?:unit_amount|price_id|priceId|price_data|stripePriceId|stripe_price_id)\b"), "code"),
    ],
    "paid": [
        ("payment-event", "strong", re.compile(r"['\"](?:checkout\.session\.(?:completed|async_payment_succeeded)|invoice\.(?:paid|payment_succeeded|payment_failed)|customer\.subscription\.(?:created|updated|deleted)|payment_intent\.succeeded|charge\.succeeded)['\"]"), "raw"),
        ("status-compare", "strong", re.compile(r"status\w*\s*(?:===?|!==?)\s*['\"](?:active|trialing|paid|past_due|canceled|cancelled|unpaid|incomplete|succeeded)['\"]|['\"](?:active|trialing|paid|past_due|canceled|cancelled|unpaid|succeeded)['\"]\s*(?:===?|!==?)\s*[\w$.]*status\b", _I), "raw"),
        ("subscription-status", "strong", re.compile(r"\b(?:subscription|sub|stripe_?subscription)\w*\??\.status\b|\b(?:subscription_?status|payment_?status|billing_?status)\b", _I), "code"),
        ("plan-compare", "strong", re.compile(r"\b(?:plan|tier|plan_?id|subscription_?tier)\w*\s*(?:===?|!==?)\s*['\"]|['\"][\w-]+['\"]\s*(?:===?|!==?)\s*[\w$.]*\b(?:plan|tier)\b", _I), "raw"),
        ("paid-check", "strong", re.compile(r"\b(?:is_?paid|has_?paid|is_?subscribed|is_?pro|is_?premium|is_?paying|has_?subscription|has_?active_?subscription|has_?paid_?plan)\b", _I), "code+cond"),
        ("paid-name", "weak", re.compile(r"\b(?:is_?paid|has_?paid|is_?subscribed|is_?pro|is_?premium|is_?paying|has_?subscription|has_?active_?subscription|has_?paid_?plan)\b", _I), "code"),
    ],
    "rounding": [
        ("money-round", "strong", re.compile(r"\bMath\.(?:round|floor|ceil|trunc)\s*\(|(?<![.\w])round\s*\(", _I), "code+money"),
        ("to-fixed", "strong", re.compile(r"\.toFixed\(\s*2\s*\)"), "code"),
        ("cents-convert", "strong", re.compile(r"[*/]\s*100\b(?!\.)"), "code+money"),
        ("currency-format", "weak", re.compile(r"Intl\.NumberFormat|style\s*:\s*['\"]currency['\"]|toLocaleString\([^)]*currency|format_?currency|number_to_currency", _I), "raw"),
        ("decimal-math", "weak", re.compile(r"\bnew\s+(?:Decimal|Big|BigNumber)\s*\(|\bDinero\s*\(|\bdinero\s*\("), "code"),
    ],
}
STOPLINE_RE = re.compile(r"(?<![a-z0-9])(ssn|social_security|dob|date_of_birth|birthdate|medical|diagnosis|credit_card|card_number|cc_number|iban|passport)(?![a-z0-9])", re.I)
CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

WARNINGS = ("stopline-hints-capped",)
PARTIAL_REASONS = ("max_files_hit", "max_total_bytes_hit", "deadline_hit", "files_errored", "files_skipped_oversize", "dirs_unreadable", "dirs_truncated", "output_trimmed")
ERROR_CODES = tuple(HINTS)
PATTERN_IDS = tuple(p[0] for t in TYPES for p in PATTERNS[t]) + tuple(t + "-comment" for t in TYPES)
VOCABULARY = frozenset(TYPES + STRENGTHS + PATTERN_IDS + tuple(STOPLINE_FIELDS) + WARNINGS + PARTIAL_REASONS
                       + ERROR_CODES + tuple(HINTS.values()) + (__version__,))


# ------------------------------------------------------------------ line reading

def blank_strings(line):
    """Empty the inside of quoted strings on one line, in one linear pass.

    Only quote and backslash positions are visited, so a line of unbalanced quotes stays linear.
    An unclosed quote leaves the rest of the line as it is.
    """
    if "'" not in line and '"' not in line and "`" not in line:
        return line
    out = []
    last = 0
    quote = None
    start = 0
    skip_to = -1
    for m in STR_CHAR_RE.finditer(line):
        p = m.start()
        if p < skip_to:
            continue
        ch = line[p]
        if quote is None:
            if ch != "\\":
                quote = ch
                start = p
        elif ch == "\\":
            skip_to = p + 2
        elif ch == quote:
            out.append(line[last:start + 1])
            last = p
            quote = None
    out.append(line[last:])
    return "".join(out)


def comment_body(stripped, ext):
    """Return the text after a comment marker when the whole line is a comment, else None."""
    if ext in (".py", ".rb"):
        markers = ("#",)
    elif ext in SQL_EXTS:
        markers = ("--",)
    else:
        markers = ("//", "/*", "*", "<!--")
    for mk in markers:
        if stripped.startswith(mk):
            return stripped[len(mk):]
    return None


def strip_trailing_comment(code, ext):
    marker = "#" if ext in (".py", ".rb") else ("--" if ext in SQL_EXTS else "//")
    i = code.find(marker)
    return code if i < 0 else code[:i]


def has_money(text):
    for ident in re.findall(IDENT, text):
        if MONEY_RE.search(ident):
            return True
    return False


def _arith_hit(code):
    if not MONEY_RE.search(code):
        return False
    target = ASSIGN_TARGET_RE.search(code)
    money_target = target is not None and MONEY_RE.search(target.group(1)) is not None
    for m in ARITH_RE.finditer(code):
        left, op, right = m.group(1), m.group(2), m.group(3)
        if not (money_target and m.start() > target.end()) and not (MONEY_RE.search(left) or MONEY_RE.search(right)):
            continue
        if op[0] in "+-" and not op.endswith("=") and not ASSIGN_CONTEXT_RE.search(code):
            continue  # page copy like "Total price - billed monthly" outside a string has no assignment
        return True
    return False


def match_type(typ, code, raw):
    """Return (pattern id, strength) for the first pattern of this type that fires, else None."""
    for pid, strength, rx, source in PATTERNS[typ]:
        if source == "arith":
            ok = _arith_hit(code)
        elif source == "money-compare":
            ok = any(MONEY_RE.search(m.group(1)) for m in rx.finditer(code))
        elif source == "price-const":
            ok = any(PRICE_CONST_IDENT_RE.search(m.group(1)) for m in rx.finditer(code))
        elif source == "raw":
            ok = rx.search(raw) is not None
        elif source == "code+cond":
            ok = rx.search(code) is not None and COND_CONTEXT_RE.search(code) is not None
        elif source == "code+money":
            ok = rx.search(code) is not None and has_money(code)
        else:
            ok = rx.search(code) is not None
        if ok:
            return pid, strength
    return None


def classify_line(line, ext):
    """Yield (type, pattern id, strength) for one source line."""
    stripped = line.strip()
    if not stripped:
        return
    body = comment_body(stripped, ext)
    if body is not None:
        for typ in TYPES:
            if match_type(typ, body, body):
                yield typ, typ + "-comment", "weak"
        return
    code = strip_trailing_comment(blank_strings(line), ext)
    raw = line
    for typ in TYPES:
        hit = match_type(typ, code, raw)
        if hit:
            yield typ, hit[0], hit[1]


# ------------------------------------------------------------------- the walk

class State:
    def __init__(self, opts):
        self.opts = opts
        self.started = time.monotonic()
        self.files_read = 0
        self.bytes_read = 0
        self.reasons = []
        self.stats = {k: 0 for k in ("files_never_open", "paths_withheld", "files_errored", "files_skipped_oversize",
                                     "files_skipped_binary", "files_skipped_generated", "files_skipped_special",
                                     "files_skipped_test", "files_skipped_env", "dirs_unreadable")}
        self.hits = {t: [] for t in TYPES}  # (rank, path, line, pattern)
        self.hints = []
        self.hints_capped = False
        self.stopped = False

    def reason(self, r):
        if r not in self.reasons:
            self.reasons.append(r)

    def over_deadline(self):
        if time.monotonic() - self.started > self.opts.deadline_s:
            self.reason("deadline_hit")
            self.stopped = True
        return self.stopped


def safe_rel(parts):
    rel = "/".join(parts)
    if len(rel) > MAX_PATH_CHARS:
        return None
    for seg in parts:
        if not SAFE_SEGMENT_RE.match(seg) or seg in (".", ".."):
            return None
    return rel


def count_never_open(path, state):
    """Count files under a never-open folder by name only; nothing inside is opened."""
    stack = [path]
    while stack and state.stats["files_never_open"] < MAX_NEVER_OPEN_COUNT:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            state.stats["files_never_open"] += 1
                    except OSError:
                        continue
        except OSError:
            continue


def read_file(path, size_hint, state):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
            return None, "special"
        if st.st_size > state.opts.max_file_bytes:
            return None, "oversize"
        chunks = []
        remaining = st.st_size + 1
        while remaining > 0:
            b = os.read(fd, min(remaining, 1 << 20))
            if not b:
                break
            chunks.append(b)
            remaining -= len(b)
        data = b"".join(chunks)
    finally:
        os.close(fd)
    if len(data) > state.opts.max_file_bytes:
        return None, "oversize"
    return data, None


def scan_file(path, parts, ext, state):
    rel = safe_rel(parts)
    data, why = read_file(path, 0, state)
    if why == "special":
        state.stats["files_skipped_special"] += 1
        return
    if why == "oversize":
        state.stats["files_skipped_oversize"] += 1
        state.reason("files_skipped_oversize")
        return
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        state.stats["files_skipped_binary"] += 1
        return
    state.files_read += 1
    state.bytes_read += len(data)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    is_schema = ext in SQL_EXTS or ext in SCHEMA_EXTS or SCHEMA_NAME_RE.search(parts[-1]) is not None
    found = []
    hints = []
    for i, line in enumerate(lines, 1):
        if i % 256 == 0 and state.over_deadline():
            break
        if line.endswith("\r"):
            line = line[:-1]
        if len(line) > LINE_CLIP_CHARS:
            line = line[:LINE_CLIP_CHARS]
        for typ, pid, strength in classify_line(line, ext):
            found.append((typ, 0 if strength == "strong" else 1, i, pid))
        if is_schema:
            seen = set()
            body = comment_body(line.strip(), ext)
            src = line if body is None else ""
            for m in STOPLINE_RE.finditer(CAMEL_SPLIT_RE.sub("_", src)):
                field = m.group(1).lower()
                if field in STOPLINE_FIELDS and field not in seen:
                    seen.add(field)
                    hints.append((i, field))
    if not found and not hints:
        return
    if rel is None:
        state.stats["paths_withheld"] += 1
        return
    for typ, rank, line_no, pid in found:
        state.hits[typ].append((rank, rel, line_no, pid))
    for line_no, field in hints:
        if len(state.hints) >= MAX_STOPLINE_HINTS:
            state.hints_capped = True
            break
        state.hints.append({"path": rel, "line": line_no, "field": field})


def walk(repo, state):
    opts = state.opts
    stack = [(repo, [])]
    while stack and not state.stopped:
        d, parts = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = []
                for n, e in enumerate(it):
                    if n >= MAX_DIR_ENTRIES:
                        state.reason("dirs_truncated")
                        break
                    entries.append(e)
        except OSError:
            state.stats["dirs_unreadable"] += 1
            state.reason("dirs_unreadable")
            continue
        entries.sort(key=lambda e: e.name)
        subdirs = []
        for e in entries:
            if state.over_deadline():
                break
            name = e.name
            try:
                is_link = e.is_symlink()
                is_dir = (not is_link) and e.is_dir(follow_symlinks=False)
            except OSError:
                state.stats["files_errored"] += 1
                state.reason("files_errored")
                continue
            if is_dir:
                if name in EXCLUDED_DIRS:
                    continue
                parent = parts[-1] if parts else ""
                if name in NEVER_OPEN_DIRS or (parent, name) in NEVER_OPEN_DIR_PAIRS:
                    count_never_open(e.path, state)
                    continue
                subdirs.append((e.path, parts + [name]))
                continue
            if name in NEVER_OPEN_FILES or NEVER_OPEN_FILE_RE.match(name):
                state.stats["files_never_open"] += 1
                continue
            lower = name.lower()
            if lower.startswith(".env"):
                state.stats["files_skipped_env"] += 1
                continue
            ext = os.path.splitext(lower)[1]
            if ext not in SCAN_EXTS:
                continue
            if is_link:
                state.stats["files_skipped_special"] += 1
                continue
            if lower in SKIP_BASENAMES or lower.endswith(SKIP_EXT_SUFFIXES):
                state.stats["files_skipped_generated"] += 1
                continue
            if TEST_FILE_RE.search(name) or any(p.lower() in TEST_DIRS for p in parts):
                state.stats["files_skipped_test"] += 1
                continue
            if state.files_read >= opts.max_files:
                state.reason("max_files_hit")
                state.stopped = True
                break
            if state.bytes_read >= opts.max_total_bytes:
                state.reason("max_total_bytes_hit")
                state.stopped = True
                break
            try:
                scan_file(e.path, parts + [name], ext, state)
            except OSError:
                state.stats["files_errored"] += 1
                state.reason("files_errored")
        for sd in reversed(subdirs):
            stack.append(sd)


# ------------------------------------------------------------------- output

def select(hits, uncapped):
    """Strong before weak, then path, then line; then round-robin across files, under the caps."""
    ordered = sorted(hits)
    by_file = {}
    file_order = []
    for h in ordered:
        if h[1] not in by_file:
            by_file[h[1]] = []
            file_order.append(h[1])
        by_file[h[1]].append(h)
    chosen = []
    rnd = 0
    while True:
        took = False
        for path in file_order:
            lst = by_file[path]
            if rnd < len(lst) and (uncapped or rnd < MAX_PER_FILE_PER_TYPE):
                if not uncapped and len(chosen) >= MAX_PER_TYPE:
                    return chosen
                chosen.append(lst[rnd])
                took = True
        if not took:
            return chosen
        rnd += 1


def build(state, uncapped):
    candidates = {}
    totals = {}
    for t in TYPES:
        hits = state.hits[t]
        chosen = select(hits, uncapped)
        candidates[t] = [{"type": t, "path": h[1], "line": h[2], "pattern": h[3], "strength": STRENGTHS[h[0]]} for h in chosen]
        totals[t] = {"listed": len(chosen), "not_listed": len(hits) - len(chosen), "files": len({h[1] for h in hits})}
    warnings_ = ["stopline-hints-capped"] if state.hints_capped else []

    def render():
        reasons = list(state.reasons)
        return {
            "ok": True,
            "partial": bool(reasons),
            "version": __version__,
            "files_read": state.files_read,
            "stats": state.stats,
            "warnings": warnings_,
            "partial_reasons": reasons,
            "stopline_hints": state.hints,
            "candidates": [c for t in TYPES for c in candidates[t]],
            "totals": totals,
        }

    result = render()
    if uncapped:
        return result
    while len(dumps(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        biggest = max(reversed(TYPES), key=lambda t: len(candidates[t]))
        if not candidates[biggest]:
            break
        candidates[biggest].pop()
        totals[biggest]["listed"] -= 1
        totals[biggest]["not_listed"] += 1
        state.reason("output_trimmed")
        result = render()
    return result


def dumps(obj):
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"))


def envelope(code):
    return {"ok": False, "error": code, "hint": HINTS.get(code, HINTS["internal"]), "partial": True}


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


class Options:
    def __init__(self, max_files, max_file_bytes, max_total_bytes, deadline_s):
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes
        self.deadline_s = deadline_s


def emit(obj):
    sys.stdout.write(dumps(obj) + "\n")
    sys.stdout.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _Parser(prog="census_scan.py", add_help=False)
    parser.add_argument("--repo")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--deadline-s", type=float, default=DEFAULT_DEADLINE_S)
    parser.add_argument("--uncapped", action="store_true")
    try:
        args = parser.parse_args(argv)
        if not args.repo:
            raise UsageError("--repo is required")
        if args.max_files < 1 or args.max_file_bytes < 1 or args.max_total_bytes < 1 or not args.deadline_s > 0:
            raise UsageError("non-positive limit")
        raw = args.repo.rstrip("/") or "/"
        if os.path.islink(raw):
            emit(envelope("repo-is-symlink"))
            return 0
        repo = os.path.realpath(raw)
        if not os.path.exists(repo):
            emit(envelope("repo-not-found"))
            return 0
        if not os.path.isdir(repo):
            emit(envelope("repo-not-a-directory"))
            return 0
        if not os.access(repo, os.R_OK | os.X_OK):
            emit(envelope("repo-unreadable"))
            return 0
        try:
            cwd = os.path.realpath(os.getcwd())
        except OSError:
            cwd = ""
        if cwd and (cwd == repo or cwd.startswith(repo.rstrip(os.sep) + os.sep)):
            emit(envelope("repo-contains-cwd"))  # never walk the launch folder or anything above it
            return 0
        state = State(Options(args.max_files, args.max_file_bytes, args.max_total_bytes, args.deadline_s))
        walk(repo, state)
        emit(build(state, args.uncapped))
        return 0
    except UsageError:
        emit(envelope("usage"))
        return 0
    except SystemExit:
        raise
    except Exception:  # last resort: never a traceback, never a path, never a message
        try:
            emit(envelope("internal"))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
