#!/usr/bin/env python3
"""build-decisions helper: lists candidate places where an app decides four things.

Read-only. Prints ONE JSON line. Nothing from inside a file ever reaches the output: every
string is a repo-relative path (only when it passes a strict character rule) or a member of
the fixed VOCABULARY below. The skill starts from the listed lines and searches the app itself.

Decision types: visibility (who can see a record), price (what something costs),
paid (whether someone has paid), rounding (how money rounds).

`--section architecture` prints a different line instead: how the app is built (shape signals with the
file that shows each, facts, one advice id) and census decisions found inside a second app that uses
the same data. Same rule: only safe paths and fixed words.
"""
__version__ = "0.5.1"

import sys

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
import base64
import fnmatch
import hashlib
import hmac
import json
import os
import re
import stat
import time


# ------------------------------------- walk rules (copied from custody-check 0.3.2, plus 0.3.3's .mts/.cts)

EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "vendor", "venv", ".venv", "__pycache__", "coverage"}
NEVER_OPEN_DIRS = {".claude", ".codex", ".agents", ".windsurf", ".clinerules", ".gemini", ".kiro", ".roo", ".trae", ".augment", ".amazonq", ".junie", ".continue", ".aider", ".opencode"}
NEVER_OPEN_DIR_PAIRS = {(".cursor", "rules"), (".github", "instructions"), (".github", "prompts"), (".github", "agents")}
NEVER_OPEN_FILE_RE = re.compile(r"^(?:claude|agents?|gemini|conventions|copilot-instructions)(?:[.-][^/]*)?\.md$|^\.aider.*$|.*\.prompt\.md$|.*\.agent\.md$|.*\.instructions\.md$|.*\.mdc$", re.I)
NEVER_OPEN_FILES = {".cursorrules", ".windsurfrules", ".clinerules", ".rules", "opencode.json", ".roomodes"}
SKIP_BASENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "cargo.lock", "composer.lock", "gemfile.lock"}
SKIP_EXT_SUFFIXES = (".map", ".min.js", ".min.css", ".bundle.js")
CODE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro", ".py", ".rb", ".go", ".java", ".kt", ".php", ".cs", ".swift", ".dart"}
SQL_EXTS = {".sql", ".psql", ".pgsql", ".ddl"}
SCHEMA_EXTS = {".prisma", ".graphql", ".gql"}
SCAN_EXTS = CODE_EXTS | SQL_EXTS | SCHEMA_EXTS
MARKUP_EXTS = {".jsx", ".tsx", ".vue", ".svelte", ".astro"}  # page copy sits outside strings here
STOPLINE_FIELDS = {"ssn", "social_security", "dob", "date_of_birth", "birthdate", "birth_date", "birthday", "medical", "diagnosis", "credit_card", "card_number", "cc_number", "iban", "passport"}
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
MAX_DEMO_KEYS = 20  # census line only: places of Supabase's public sample keys
DEFAULT_MAX_FILES = 20000
DEFAULT_MAX_FILE_BYTES = 524288
DEFAULT_MAX_TOTAL_BYTES = 268435456
DEFAULT_DEADLINE_S = 90.0  # under the 120 s a host gives one shell command, so a slow scan still prints its partial result
DEADLINE_LINE_TICK = 32
SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._@+()\[\]-]+$")
TEST_FILE_RE = re.compile(r"[._-](?:test|spec)\.[A-Za-z0-9]+$", re.I)
TEST_DIRS = {"__tests__", "__mocks__", "tests", "test", "spec", "e2e", "cypress", "playwright"}
SCHEMA_NAME_RE = re.compile(r"schema|model|types|entities", re.I)

# Recall first: a money word anywhere in an identifier counts (unitprice, grandtotal, baseFee), because a
# wrong candidate costs one window and a missed one is never seen. Known non-money words that contain a
# money word are removed before the match, so feedback is not a fee and syntax is not a tax.
MONEY_RE = re.compile(r"price|amount|total|cost|fee|tax|discount|cents|charge|balance|payout|refund", re.I)
PRICE_CONST_RE = re.compile(r"price|cost|fee|amount|tax", re.I)
NOT_MONEY_RE = re.compile(r"feedback|feed|feel|coffee|toffee|chargeback|syntax|taxonom|taxi|costume|loadbalanc|discharg", re.I)
# Every identifier pattern starts at an identifier boundary, so a long word costs one try, not one per character.
IDENT = r"(?<![\w$])[A-Za-z_$][\w$]*"
IDENT_ANY_RE = re.compile(IDENT)
DOTTED = r"(?<![\w$])[A-Za-z_$][\w$.]*"
# identifier, an arithmetic operator, an operand. "-" never starts "->" or "--"; "/" never starts a comment.
ARITH_RE = re.compile(r"(" + DOTTED + r")\s*(\*=?|/=?(?![/*])|\+=?(?!\+)|-=?(?![->]))\s*(" + DOTTED + r"|\d[\d_.]*|\()")
# "shippingCost = weight * 0.5": arithmetic assigned to a money-named target counts even when no operand is money.
ASSIGN_TARGET_RE = re.compile(r"(" + IDENT + r")\s*(?::[^=]{0,40})?(?<![=!<>])=(?![=>])")
ASSIGN_CONTEXT_RE = re.compile(r"(?<![=!<>])=(?![=>])|\breturn\b|\(")
OWNER_FIELD = r"(?:owner_?id|user_?id|author_?id|created_?by|tenant_?id|org_?id|account_?id)"
COND_CONTEXT_RE = re.compile(r"\bif\b|&&|\|\||\?|\breturn\b|!\s*[\w$.]|\bwhile\b|\bfilter\b|\bwhere\b|\bunless\b|\bwhen\b")
STR_CHAR_RE = re.compile(r"[\"'`\\]")
TEMPLATE_EXPR_RE = re.compile(r"\$\{[^{}]*\}")
STRING_PREFIXES = {"f", "r", "b", "u", "rb", "br", "fr", "rf"}

# (pattern id, strength, compiled regex, source). Sources: "code" (strings blanked, trailing comment cut),
# "raw" (the line as written), "code+cond" (also in a condition), "code+money" (also a money-named identifier),
# and the named checks in match_type.
_I = re.I
PATTERNS = {
    "visibility": [
        ("role-compare", "strong", re.compile(r"\brole\w*\s*(?:===?|!==?)|(?:===?|!==?)\s*[\w$.]*\.role\b|\bhas_?role\s*\(", _I), "code"),
        ("owner-compare", "strong", re.compile(r"(?:owner_?id|user_?id|author_?id|created_?by|tenant_?id|org_?id|account_?id)\s*(?:===?|!==?)|(?:===?|!==?)\s*[\w$.]*(?:owner_?id|user_?id|author_?id|created_?by|tenant_?id|org_?id|account_?id)\b", _I), "code"),
        ("owner-filter", "strong", re.compile(r"\.eq\(\s*['\"](?:user_id|owner_id|author_id|tenant_id|org_id|account_id)['\"]|\bwhere\s*:\s*\{\s*(?:userId|ownerId|authorId|tenantId|orgId|user_id|owner_id)\b", _I), "raw"),
        ("row-policy", "strong", re.compile(r"\bcreate\s+policy\b|\bauth\.uid\s*\(\s*\)", _I), "raw"),
        ("owner-query", "strong", re.compile(r"\b(?:select|update|delete)\b[^;]{0,200}?\bwhere\b[^;]{0,200}?\b(?:owner_id|user_id|author_id|tenant_id|org_id|account_id)\s*=(?!=)", _I), "raw"),
        ("owner-orm-filter", "strong", re.compile(r"\beq\(\s*[\w$]+\." + OWNER_FIELD + r"\b|\bwhere\(\s*['\"](?:ownerId|userId|authorId|uid|owner_id|user_id|author_id)['\"]\s*,\s*['\"]==|\b(?:find|findOne|findMany|findFirst|findUnique|count|deleteMany|updateMany)\w*\(\s*\{[^}]*\b(?:ownerId|userId|authorId|tenantId|orgId|owner_id|user_id|author_id)\s*:", _I), "raw"),
        ("owner-where-field", "strong", re.compile(r"^\s*(?:ownerId|userId|authorId|tenantId|orgId|owner_id|user_id|author_id)\s*:\s*[\w$.]*\b(?:user|session|auth|uid|req|me|currentUser)\b", _I), "raw+where"),
        ("access-check", "strong", re.compile(r"\b(?:can_?view|can_?access|can_?read|can_?see|can_?edit|can_?delete|has_?access|has_?permission|is_?allowed|authorize)\w*\s*\(", _I), "code"),
        ("visibility-compare", "strong", re.compile(r"\b(?:is_?public|is_?private|visibility|is_?published)\s*(?:===?|!==?)", _I), "code"),
        ("admin-check", "strong", re.compile(r"\b(?:is_?admin|is_?super_?admin|is_?superuser|is_?staff|is_?owner|is_?moderator)\b|\.(?:admin|superuser|staff|owner|moderator)\?(?![.\w(\[])", _I), "code+cond"),
        ("admin-name", "weak", re.compile(r"\b(?:is_?admin|is_?super_?admin|is_?superuser|is_?staff|is_?owner|is_?moderator)\b", _I), "code"),
    ],
    "price": [
        ("price-arith", "strong", None, "arith"),
        ("price-compare", "strong", re.compile(r"(" + IDENT + r")\s*(?:[<>]=?)\s*\d"), "money-compare"),
        ("discount-rule", "strong", re.compile(r"\b\w*(?:discount|coupon|percent_?off)\w*\s*(?:[<>]=?|===?|!==?)", _I), "code"),
        ("price-constant", "weak", re.compile(r"(" + IDENT + r")\s*[:=](?!=)\s*-?\d[\d_.]*\b"), "price-const"),
        ("price-table", "weak", re.compile(r"(" + IDENT + r")\s*(?::[^=]{0,40})?(?<![=!<>])=(?![=>])\s*\{[^}]*\b\w+\s*:\s*\d"), "price-const"),
        ("price-decimal", "weak", re.compile(r"(" + IDENT + r")\s*(?::[^=]{0,40})?(?<![=!<>])=(?![=>])\s*(?:new\s+)?(?:Decimal|BigDecimal|Money|Big|BigNumber)\(\s*['\"]?-?\d"), "price-const-raw"),
        ("billing-price-id", "weak", re.compile(r"\b(?:unit_amount|price_id|priceId|price_data|stripePriceId|stripe_price_id)\b"), "code"),
    ],
    "paid": [
        ("payment-event", "strong", re.compile(r"['\"](?:checkout\.session\.(?:completed|async_payment_succeeded)|invoice\.(?:paid|payment_succeeded|payment_failed)|customer\.subscription\.(?:created|updated|deleted)|payment_intent\.succeeded|charge\.succeeded)['\"]"), "raw"),
        ("status-compare", "strong", re.compile(r"status\w*\s*(?:===?|!==?)\s*['\"](?:active|trialing|paid|past_due|canceled|cancelled|unpaid|incomplete|succeeded)['\"]|['\"](?:active|trialing|paid|past_due|canceled|cancelled|unpaid|succeeded)['\"]\s*(?:===?|!==?)\s*[\w$.]*status\b", _I), "raw"),
        ("subscription-status", "strong", re.compile(r"\b(?:subscription|sub|stripe_?subscription)\w*\??\.status\b|\b(?:subscription_?status|payment_?status|billing_?status)\b", _I), "code"),
        ("paid-flag-compare", "strong", re.compile(r"\.(?:paid|is_?paid|has_?paid)\s*(?:===?|!==?)\s*(?:true|false)\b|\bif\s*\(?\s*!?\s*[\w$]+(?:\.[\w$]+)*\.(?:paid|is_?paid)\b", _I), "code"),
        ("plan-compare", "strong", re.compile(r"\b(?:plan|tier|plan_?id|subscription_?tier)\w*\s*(?:===?|!==?)\s*['\"]|['\"][\w-]+['\"]\s*(?:===?|!==?)\s*[\w$.]*\b(?:plan|tier)\b", _I), "raw"),
        ("paid-check", "strong", re.compile(r"\b(?:is_?paid|has_?paid|is_?subscribed|is_?pro|is_?premium|is_?paying|has_?subscription|has_?active_?subscription|has_?paid_?plan)\b", _I), "code+cond"),
        ("paid-name", "weak", re.compile(r"\b(?:is_?paid|has_?paid|is_?subscribed|is_?pro|is_?premium|is_?paying|has_?subscription|has_?active_?subscription|has_?paid_?plan)\b", _I), "code"),
    ],
    "rounding": [
        ("money-round", "strong", re.compile(r"\bMath\.(?:round|floor|ceil|trunc)\s*\(|(?<![.\w])round\s*\(", _I), "code+money"),
        ("to-fixed", "strong", re.compile(r"\.toFixed\(\s*2\s*\)"), "code"),
        ("cents-convert", "strong", re.compile(r"[*/]\s*100\b(?!\.)"), "code+money"),
        ("decimal-round", "strong", re.compile(r"\.quantize\s*\(\s*(?:Decimal|D)\(|\brounding\s*=|\bROUND_HALF_\w+|\bROUND_(?:UP|DOWN|CEILING|FLOOR)\b|\.setScale\s*\(|\bRoundingMode\.\w+"), "code"),
        ("currency-format", "weak", re.compile(r"Intl\.NumberFormat|style\s*:\s*['\"]currency['\"]|toLocaleString\([^)]*currency|format_?currency|number_to_currency", _I), "raw"),
        ("decimal-math", "weak", re.compile(r"\bnew\s+(?:Decimal|Big|BigNumber)\s*\(|\bDinero\s*\(|\bdinero\s*\("), "code"),
    ],
}
STOPLINE_RE = re.compile(r"(?<![a-z0-9])(ssn|social_security|dob|date_of_birth|birthdate|birth_date|birthday|medical|diagnosis|credit_card|card_number|cc_number|iban|passport)(?![a-z0-9])", re.I)
CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

# Supabase's local development setup ships sample keys that are public by design: they are signed with a
# secret printed in Supabase's own docs and carry iss "supabase-demo". A token counts as a sample key only when
# BOTH hold: the label alone can be copied onto any key, the public signature cannot. A line is listed only when
# every token on it is a sample key and nothing else on it looks like a key, so a real key is never quieted.
# JWT_RE is custody-check's pattern, text for text (a test compares them).
SAMPLE_JWT_SECRET = b"super-secret-jwt-token-with-at-least-32-characters-long"
SAMPLE_JWT_ISS = "supabase-demo"
MAX_JWT_PAYLOAD = 4096
JWT_RE = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])")
OTHER_KEY_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sb_secret_[A-Za-z0-9_-]{10,}"
    r"|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{22,}|gh[ousr]_[A-Za-z0-9]{36}"
    r"|xox[baprs]-|xapp-|eyJ|-----BEGIN")
LONG_RUN_RE = re.compile(r"[A-Za-z0-9_\-+/=]{32,}")


def _b64(part):
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def is_sample_key(token):
    """True only for a JWT signed with Supabase's public sample secret whose payload says iss supabase-demo."""
    try:
        if not isinstance(token, str) or not JWT_RE.fullmatch(token):
            return False
        head, body, sig = token.split(".")
        if len(body) > MAX_JWT_PAYLOAD:
            return False
        want = hmac.new(SAMPLE_JWT_SECRET, (head + "." + body).encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(want, _b64(sig)):
            return False
        claims = json.loads(_b64(body).decode("utf-8"))
        return isinstance(claims, dict) and claims.get("iss") == SAMPLE_JWT_ISS
    except Exception:  # any odd token is "not a sample key": the key is then reported as before
        return False


def _looks_like_key(text):
    if OTHER_KEY_RE.search(text):
        return True
    for m in LONG_RUN_RE.finditer(text):
        run = m.group(0)
        kinds = sum(1 for test in (str.islower, str.isupper, str.isdigit) if any(test(c) for c in run))
        if kinds >= 3:
            return True
    return False


def line_has_only_sample_keys(line):
    """A line is listed only when it holds at least one token, every token is a sample key, and nothing else
    on it looks like a key. Anything unsure stays unlisted, so the skill reports it as before."""
    if "eyJ" not in line:
        return False
    rest = []
    pos = 0
    for m in JWT_RE.finditer(line):
        if not is_sample_key(m.group(0)):
            return False
        rest.append(line[pos:m.start()])
        pos = m.end()
    rest.append(line[pos:])
    return len(rest) > 1 and not _looks_like_key(" ".join(rest))


WARNINGS = ("stopline-hints-capped",)
PARTIAL_REASONS = ("max_files_hit", "max_total_bytes_hit", "deadline_hit", "files_errored", "files_skipped_oversize",
                   "files_skipped_special", "dirs_unreadable", "dirs_truncated", "output_trimmed")
ERROR_CODES = tuple(HINTS)
PATTERN_IDS = tuple(p[0] for t in TYPES for p in PATTERNS[t]) + tuple(t + "-comment" for t in TYPES)
VOCABULARY_CENSUS = (TYPES + STRENGTHS + PATTERN_IDS + tuple(STOPLINE_FIELDS) + WARNINGS + PARTIAL_REASONS
                     + ERROR_CODES + tuple(HINTS.values()) + (__version__,))


# ------------------------------------------------------------------ line reading

def blank_strings(line):
    """Empty the inside of quoted strings on one line, in one linear pass.

    Only quote and backslash positions are visited, so a line of unbalanced quotes stays linear.
    A quote right after a letter or digit is an apostrophe (You'll, that's), not a string, except a
    one- or two-letter string prefix (f"", rb''). Code inside a template literal's ${...} is kept.
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
            if ch == "\\":
                continue
            if p > 0 and (line[p - 1].isalnum() or line[p - 1] == "_") and not _string_prefix(line, p):
                continue
            quote = ch
            start = p
        elif ch == "\\":
            skip_to = p + 2
        elif ch == quote:
            out.append(line[last:start + 1])
            if quote == "`":
                out.append(" ".join(blank_strings(e) for e in TEMPLATE_EXPR_RE.findall(line[start + 1:p])))
            last = p
            quote = None
    out.append(line[last:])
    return "".join(out)


def _string_prefix(line, p):
    """True when the letters before a quote are a string prefix such as f, r, b, rb, fr."""
    i = p
    while i > 0 and line[i - 1].isalpha() and p - i < 2:
        i -= 1
    if i > 0 and (line[i - 1].isalnum() or line[i - 1] == "_"):
        return False
    return line[i:p].lower() in STRING_PREFIXES


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


def is_money(ident, words=MONEY_RE):
    """True when the identifier holds a money word once known non-money words are taken out."""
    return words.search(NOT_MONEY_RE.sub(" ", ident)) is not None


def has_money(text):
    return any(is_money(m.group(0)) for m in IDENT_ANY_RE.finditer(text))


def _arith_hit(code, prose):
    """Arithmetic on money. prose is True for markup and comments, where words sit outside strings:
    there a + or - needs an assignment, return or call on the line, and so does any operator in a comment."""
    if not has_money(code):
        return False
    target = ASSIGN_TARGET_RE.search(code)
    money_target = target is not None and is_money(target.group(1))
    for m in ARITH_RE.finditer(code):
        left, op, right = m.group(1), m.group(2), m.group(3)
        if not (money_target and m.start() > target.end()) and not (is_money(left) or is_money(right)):
            continue
        if prose and op[0] in "+-" and not op.endswith("=") and not ASSIGN_CONTEXT_RE.search(code):
            continue  # page copy like "Total price - billed monthly" written outside a string
        return True
    return False


def match_type(typ, code, raw, prose=False, where_ctx=False):
    """Return (pattern id, strength) for the first pattern of this type that fires, else None."""
    for pid, strength, rx, source in PATTERNS[typ]:
        if source == "arith":
            ok = _arith_hit(code, prose)
        elif source == "money-compare":
            ok = any(is_money(m.group(1)) for m in rx.finditer(code))
        elif source == "price-const":
            ok = any(is_money(m.group(1), PRICE_CONST_RE) for m in rx.finditer(code))
        elif source == "price-const-raw":
            ok = any(is_money(m.group(1), PRICE_CONST_RE) for m in rx.finditer(raw))
        elif source == "raw":
            ok = rx.search(raw) is not None
        elif source == "raw+where":
            ok = where_ctx and rx.search(raw) is not None
        elif source == "code+cond":
            ok = rx.search(code) is not None and COND_CONTEXT_RE.search(code) is not None
        elif source == "code+money":
            ok = rx.search(code) is not None and has_money(code)
        else:
            ok = rx.search(code) is not None
        if ok:
            return pid, strength
    return None


WHERE_OPEN_RE = re.compile(r"\bwhere\s*:\s*\{\s*$")


def classify_line(line, ext, where_ctx=False):
    """Yield (type, pattern id, strength) for one source line. where_ctx: a recent line opened `where: {`."""
    stripped = line.strip()
    if not stripped:
        return
    body = comment_body(stripped, ext)
    if body is not None:
        if not ASSIGN_CONTEXT_RE.search(body):
            return  # prose ("the cost/timing aggregates"), not a decider left in a comment
        for typ in TYPES:
            if match_type(typ, body, body, prose=True):
                yield typ, typ + "-comment", "weak"
        return
    code = strip_trailing_comment(blank_strings(line), ext)
    raw = line
    prose = ext in MARKUP_EXTS
    for typ in TYPES:
        hit = match_type(typ, code, raw, prose, where_ctx)
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
        self.collect_demo_keys = True  # census only; the section scans turn it off
        self.demo_keys = []
        self.demo_keys_capped = False

    def reason(self, r):
        if r not in self.reasons:
            self.reasons.append(r)

    # Hooks for a section scan (ArchState). The census uses none of them, so its line never changes.
    def on_dir(self, parts):
        pass

    def on_meta(self, path, parts, lower, is_link):
        return False

    def on_lines(self, parts, ext, lines):
        pass

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
    seen = 0
    while stack and seen < MAX_NEVER_OPEN_COUNT and not state.over_deadline():
        d = stack.pop()
        seen += 1
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        seen += 1
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            state.stats["files_never_open"] += 1
                    except OSError:
                        continue
        except OSError:
            continue


def read_file(path, state, cap=None):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
            return None, "special"
        cap = state.opts.max_file_bytes if cap is None else cap
        if st.st_size > cap:
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
    if len(data) > cap:
        return None, "oversize"
    return data, None


def scan_file(path, parts, ext, state):
    rel = safe_rel(parts)
    data, why = read_file(path, state)
    if why == "special":
        state.stats["files_skipped_special"] += 1
        state.reason("files_skipped_special")
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
    state.on_lines(parts, ext, lines)
    is_schema = ext in SQL_EXTS or ext in SCHEMA_EXTS or SCHEMA_NAME_RE.search(parts[-1]) is not None
    found = []
    hints = []
    demo_lines = []
    where_open = 0
    for i, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        if len(line) > LINE_CLIP_CHARS:
            line = line[:LINE_CLIP_CHARS]
        if (i % DEADLINE_LINE_TICK == 0 or len(line) > 512) and state.over_deadline():
            break
        if state.collect_demo_keys and line_has_only_sample_keys(line):
            demo_lines.append(i)
        for typ, pid, strength in classify_line(line, ext, where_open > 0):
            found.append((typ, 0 if strength == "strong" else 1, i, pid))
        where_open = 3 if WHERE_OPEN_RE.search(line) else max(0, where_open - 1)
        if is_schema:
            seen = set()
            body = comment_body(line.strip(), ext)
            src = strip_trailing_comment(line, ext) if body is None else ""
            for m in STOPLINE_RE.finditer(CAMEL_SPLIT_RE.sub("_", src)):
                field = m.group(1).lower()
                if field in STOPLINE_FIELDS and field not in seen:
                    seen.add(field)
                    hints.append((i, field))
    if rel is not None:
        for line_no in demo_lines:
            if len(state.demo_keys) >= MAX_DEMO_KEYS:
                state.demo_keys_capped = True
                break
            state.demo_keys.append({"path": rel, "line": line_no})
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
                state.on_dir(parts + [name])
                subdirs.append((e.path, parts + [name]))
                continue
            if name in NEVER_OPEN_FILES or NEVER_OPEN_FILE_RE.match(name):
                state.stats["files_never_open"] += 1
                continue
            lower = name.lower()
            if lower.startswith(".env"):
                state.stats["files_skipped_env"] += 1
                continue
            if state.on_meta(e.path, parts + [name], lower, is_link):
                continue
            ext = os.path.splitext(lower)[1]
            if ext not in SCAN_EXTS:
                continue
            if is_link:
                state.stats["files_skipped_special"] += 1
                state.reason("files_skipped_special")
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


# ------------------------------------------------------- section: how the app is built
#
# `--section architecture` runs its own walk (own State, counters, deadline and output cap) and prints
# one line: shape signals with the file that shows each, facts, one advice id picked by a fixed rule
# order, and census decisions found inside a second app that uses the same data. Nothing from inside
# a file reaches the output: only safe paths and the words below. App text (globs, route paths, called
# paths) is never compiled into a regex: it is matched one path segment at a time.

SECTIONS = ("architecture", "payment")
SIGNALS = ("baas-from-browser", "own-api-routes", "server-actions", "separate-backend", "second-client")
FACTS = ("mobile-app", "multi-frontend", "api-key-routes")
ADVICE = ("shared-api", "each-entry-checks", "one-server-place")
COVERAGE = ("complete", "partial", "not_determined")
ARCH_KINDS = ("decision-in-client-app",)
APP_KINDS = ("mobile-app", "web-app")
ARCH_REASONS = ("apps_capped", "links_capped")
MAX_PER_SIGNAL = 25
MAX_META_BYTES = 262144
MAX_META_FILES = 500
MAX_ROUTE_PATHS = 2000
MAX_LINK_PATHS = 2000
MAX_APPS = 50
MAX_NATIVE_DIRS = 200
MAX_GLOBS = 200
MAX_GLOB_CHARS = 200
MAX_PATH_SEGS = 30
MAX_DIRECTIVE_LINES = 5  # 'use client' counts only near the top of a file
POST_WALK_BUDGET_S = 10.0  # after the 90 s walk: still under the 120 s a host gives one command

META_BASENAMES = {"package.json", "app.json", "pnpm-workspace.yaml"}
NATIVE_MARKERS = {"podfile", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}
NOT_APP_DIRS = TEST_DIRS | {"fixtures", "__fixtures__", "examples", "example"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro"}
NATIVE_EXTS = {".swift", ".kt", ".java", ".dart"}
COMPONENT_EXTS = {".svelte", ".vue"}  # components: their handlers run in the browser in every framework
ROUTE_FILE_RE = re.compile(r"^route\.(?:js|jsx|ts|tsx|mjs|mts|cjs|cts)$")
SERVER_SEGMENTS = {"api", "server", "backend", "functions", "supabase", "scripts", "lambda", "lambdas", "worker",
                   "workers", "cron", "jobs", "edge", "netlify", "convex"}
SERVER_NAME_RE = re.compile(r"(?:^|\.)server\.|^\+server\.|^middleware\.|^route\.|^proxy\.")
BACKEND_DIRS = {"server", "backend", "api"}
NODE_SERVER_DEPS = {"express", "fastify", "hono", "@nestjs/core", "koa"}
BAAS_DEPS = {"@supabase/supabase-js": "supabase", "@supabase/ssr": "supabase", "firebase": "firebase"}
# A root whose code runs in the browser unless a file says otherwise, and the frameworks that run pages and
# loaders on the server by default (there only an explicit browser marker counts).
BROWSER_DEPS = {"react-dom", "vue", "svelte", "preact", "solid-js", "@angular/core", "vite", "react-scripts"}
SERVER_RENDER_DEPS = {"next", "nuxt", "astro", "@sveltejs/kit", "@remix-run/node", "@remix-run/react", "@remix-run/dev",
                      "@react-router/dev", "@react-router/node", "@solidjs/start", "@tanstack/react-start",
                      "@tanstack/start"}
WEB_FRAMEWORK_DEPS = {"next", "nuxt", "@sveltejs/kit", "@remix-run/react", "@react-router/dev"}
WEB_RUNTIME_DEPS = {"react-dom", "vue", "svelte", "preact", "solid-js"}
NOT_FRONTEND_DEPS = {"nextra", "@docusaurus/core", "docusaurus", "vitepress", "astro", "react-email",
                     "@react-email/components"}
MOBILE_DEPS = {"react-native", "expo"}

USE_CLIENT_RE = re.compile(r"""^\s*['"]use client['"]\s*;?\s*$""")
USE_SERVER_RE = re.compile(r"""^\s*['"]use server['"]\s*;?\s*$""")
BAAS_IMPORT_RE = re.compile(r"""^\s*(?!import\s+type\b)(?:import\b[^'"]*|.*\brequire\(\s*|export\b[^'"]*from\s*)['"]"""
                            r"""(@supabase/(?:supabase-js|ssr|auth-helpers-[\w-]+)|firebase(?:/(?:app|firestore|database|auth|storage))?)['"]""")
# A database read or write, not set-up or sign-in: <client>.from('table'), <client>.rpc('fn'),
# <client>.storage.from(...). The receiver must be a Supabase client: a name holding "supabase", or a
# name the file assigns from a client factory; or the factory call itself, chained.
CLIENT_FACTORIES = r"(?:createClient|createBrowserClient|createServerClient|useSupabaseClient|createClientComponentClient|createPagesBrowserClient)"
CLIENT_ASSIGN_RE = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]{0,40})?=\s*(?:await\s+)?" + CLIENT_FACTORIES + r"\s*[(<]")
RECEIVER_CALL_RE = re.compile(r"""(?<![\w$])([A-Za-z_$][\w$]*)\s*\.\s*(?:storage\s*\.\s*)?(?:from|rpc)\s*\(\s*['"`]""")
LEADING_CALL_RE = re.compile(r"""^\s*\.\s*(?:storage\s*\.\s*)?(?:from|rpc)\s*\(\s*['"`]""")
TRAILING_NAME_RE = re.compile(r"(?<![\w$])([A-Za-z_$][\w$]*)\s*$")
CHAINED_FACTORY_CALL_RE = re.compile(r"\b" + CLIENT_FACTORIES + r"""\s*\([^()]*\)\s*\.\s*(?:from|rpc)\s*\(\s*['"`]""")
FIRESTORE_SHAPED_RE = re.compile(r"\b(?:getDocs?|addDoc|setDoc|updateDoc|deleteDoc|onSnapshot)\s*\(\s*(?:collection|collectionGroup|doc|query)\s*\(")
FIRESTORE_NAME_RE = re.compile(r"\b(?:getDocs?|addDoc|setDoc|updateDoc|deleteDoc|onSnapshot)\s*\(")
BROWSER_CLIENT_RE = re.compile(r"\bcreateBrowserClient\s*\(")
# The closing line of an import formatted over several lines: `} from "firebase/firestore";`
BAAS_IMPORT_CLOSE_RE = re.compile(r"""^\s*\}\s*from\s*['"](@supabase/(?:supabase-js|ssr|auth-helpers-[\w-]+)|firebase(?:/(?:app|firestore|database|auth|storage))?)['"]""")
NATIVE_BAAS_RE = re.compile(r"^\s*import\s+(?:Supabase|FirebaseFirestore|FirebaseDatabase|Firebase)\b|"
                            r"^\s*import\s+(?:io\.github\.jan\.supabase|com\.google\.firebase\.(?:firestore|database))\b|"
                            r"""^\s*import\s+['"]package:(?:supabase_flutter|supabase|cloud_firestore|firebase_database)/""")
NODE_SERVER_IMPORT_RE = re.compile(r"""(?:from\s+|require\(\s*)['"](?:express|fastify|hono|koa)['"]""")
NODE_ROUTE_RE = re.compile(r"""\b(?:app|router|server|api|fastify|route)\s*\.\s*(?:get|post|put|patch|delete|all)\s*\(\s*['"`](/[^'"`\s]*)""")
PY_SERVER_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+(?:flask|fastapi)\b")
PY_ROUTE_RE = re.compile(r"""^\s*@\w+\.(?:route|get|post|put|patch|delete)\(\s*['"](/[^'"]*)""")
FETCH_RE = re.compile(r"""\b(?:fetch|axios(?:\.(?:get|post|put|patch|delete|request))?|ky(?:\.\w+)?)\s*\(\s*['"`](?:https?://[^/'"`\s]+)?(/api/[^'"`?#\s$]*)""")
API_URL_RE = re.compile(r"""['"](?:https?://[^/'"\s]+)(/api/[^'"?#\s]*)""")
API_KEYS_RE = re.compile(r"(?:^|/)api[-_]?keys?(?:/|$)", re.I)
EXPO_CONFIG_RE = re.compile(r"\bexpo\b")
WORKSPACE_LINE_RE = re.compile(r"""^\s*-\s*['"]?([^'"#\s]+)['"]?\s*(?:#.*)?$""")


def _not_app(parts):
    return any(p.lower() in NOT_APP_DIRS for p in parts)


class FileFacts:
    __slots__ = ("rel", "parts", "ext", "use_client", "use_server", "baas", "baas_call", "browser_client",
                 "routes", "links", "node_server", "py_server")

    def __init__(self, rel, parts, ext):
        self.rel, self.parts, self.ext = rel, parts, ext
        self.use_client = self.use_server = self.baas_call = self.browser_client = False
        self.node_server = self.py_server = False
        self.baas = set()
        self.routes = []
        self.links = []


class ArchState(State):
    """A census walk that also records how the app is built."""

    def __init__(self, opts):
        State.__init__(self, opts)
        self.collect_demo_keys = False
        self.stats.update({"manifests_read": 0, "manifests_unreadable": 0})
        self.files = []
        self.manifests = {}  # dir parts tuple -> parsed package.json dict
        self.expo_dirs = set()
        self.flutter_dirs = set()
        self.wrapper_dirs = set()  # dir parts with capacitor.config.* or src-tauri/
        self.native_dirs = []  # parts of ios/ and android/ folders
        self.native_marked = set()  # every prefix of a folder holding an Xcode or Gradle project file
        self.workspace_globs = None
        self.route_count = 0
        self.link_count = 0

    def mark_native(self, d):
        for k in range(1, len(d) + 1):
            self.native_marked.add(tuple(d[:k]))

    def on_dir(self, parts):
        if _not_app(parts):
            return
        name = parts[-1]
        if name == "src-tauri":
            self.wrapper_dirs.add(tuple(parts[:-1]))
        elif name in ("ios", "android"):
            if len(self.native_dirs) < MAX_NATIVE_DIRS:
                self.native_dirs.append(tuple(parts))
            else:
                self.reason("apps_capped")
        elif name.endswith((".xcodeproj", ".xcworkspace")):
            self.mark_native(parts[:-1])

    def meta_unreadable(self):
        self.stats["manifests_unreadable"] += 1

    def on_meta(self, path, parts, lower, is_link):
        d = tuple(parts[:-1])
        if _not_app(d):
            return lower in META_BASENAMES
        if lower.startswith("capacitor.config."):
            self.wrapper_dirs.add(d)
        if lower in NATIVE_MARKERS:
            self.mark_native(d)
        if lower == "pubspec.yaml":
            self.flutter_dirs.add(d)
        if lower not in META_BASENAMES:
            return False
        if is_link:
            self.stats["files_skipped_special"] += 1
            self.reason("files_skipped_special")
            return True
        if self.stats["manifests_read"] + self.stats["manifests_unreadable"] >= MAX_META_FILES:
            self.meta_unreadable()
            return True
        try:
            data, _ = read_file(path, self, cap=MAX_META_BYTES)
        except OSError:
            data = None
        if data is None:
            self.meta_unreadable()
            return True
        text = data.decode("utf-8", errors="replace")
        if lower == "pnpm-workspace.yaml":
            self.stats["manifests_read"] += 1
            if not d:
                self.workspace_globs = (self.workspace_globs or []) + _pnpm_globs(text)
            return True
        try:
            obj = json.loads(text)
        except ValueError:
            self.meta_unreadable()
            return True
        if not isinstance(obj, dict):
            self.meta_unreadable()
            return True
        self.stats["manifests_read"] += 1
        if lower == "app.json":
            if isinstance(obj.get("expo"), dict):
                self.expo_dirs.add(d)
            return True
        self.manifests[d] = obj
        if not d:
            ws = obj.get("workspaces")
            if isinstance(ws, dict):
                ws = ws.get("packages")
            if isinstance(ws, list):
                self.workspace_globs = (self.workspace_globs or []) + [g for g in ws if isinstance(g, str)]
        return True

    def on_lines(self, parts, ext, lines):
        rel = safe_rel(parts)
        if rel is None or _not_app(parts[:-1]):
            return
        name = parts[-1].lower()
        ff = FileFacts(rel, tuple(parts), ext)
        expo_cfg = name.startswith("app.config.")
        route = _file_route(parts) if ext in JS_EXTS else None
        if route is not None:
            ff.routes.append(route)
        seen_code = 0
        firestore_named = False
        receivers = set()  # names a .from('x') / .rpc('x') call was made on
        clients = set()  # names the file assigns from a Supabase client factory
        prev_tail = None  # the last name on the previous code line, for chains split over lines
        for line in lines:
            if len(line) > LINE_CLIP_CHARS:
                line = line[:LINE_CLIP_CHARS]
            stripped = line.strip()
            if not stripped:
                continue
            if seen_code < MAX_DIRECTIVE_LINES and USE_CLIENT_RE.match(line):
                ff.use_client = True
            if USE_SERVER_RE.match(line):
                ff.use_server = True
            if comment_body(stripped, ext) is not None:
                continue
            seen_code += 1
            if expo_cfg and EXPO_CONFIG_RE.search(line):
                self.expo_dirs.add(tuple(parts[:-1]))
            if ext in JS_EXTS:
                m = BAAS_IMPORT_RE.match(line) or BAAS_IMPORT_CLOSE_RE.match(line)
                if m:
                    ff.baas.add("supabase" if m.group(1).startswith("@supabase") else "firebase")
                for m in CLIENT_ASSIGN_RE.finditer(line):
                    clients.add(m.group(1))
                for m in RECEIVER_CALL_RE.finditer(line):
                    receivers.add(m.group(1))
                if LEADING_CALL_RE.match(line) and prev_tail:
                    receivers.add(prev_tail)
                if CHAINED_FACTORY_CALL_RE.search(line):
                    ff.baas_call = True
                m = TRAILING_NAME_RE.search(line)
                prev_tail = m.group(1) if m else None
                if FIRESTORE_SHAPED_RE.search(line):
                    ff.baas_call = True
                elif FIRESTORE_NAME_RE.search(line):
                    firestore_named = True
                if BROWSER_CLIENT_RE.search(line):
                    ff.browser_client = True
                if NODE_SERVER_IMPORT_RE.search(line):
                    ff.node_server = True
                for m in NODE_ROUTE_RE.finditer(line):
                    ff.routes.append(("node", m.group(1)))
                for m in FETCH_RE.finditer(line):
                    ff.links.append(m.group(1))
            elif ext == ".py":
                if PY_SERVER_IMPORT_RE.match(line):
                    ff.py_server = True
                m = PY_ROUTE_RE.match(line)
                if m:
                    ff.routes.append(("py", m.group(1)))
            elif ext in NATIVE_EXTS and NATIVE_BAAS_RE.match(line):
                ff.baas.add("supabase" if "upabase" in line else "firebase")
            for m in API_URL_RE.finditer(line):
                ff.links.append(m.group(1))
        # A data call counts only with evidence of which database: .from('x') needs a Supabase client as its
        # receiver; a Firestore-named call needs a Firestore import or a collection()/doc() argument.
        if any("supabase" in r.lower() or r in clients for r in receivers):
            ff.baas_call = True
        if not ff.baas_call and firestore_named and "firebase" in ff.baas:
            ff.baas_call = True
        # framework-call routes only count where the file uses that framework
        ff.routes = [r for r in ff.routes if r[0] == "file" or (r[0] == "node" and ff.node_server)
                     or (r[0] == "py" and ff.py_server)]
        room_r, room_l = MAX_ROUTE_PATHS - self.route_count, MAX_LINK_PATHS - self.link_count
        if len(ff.routes) > room_r or len(ff.links) > room_l:
            self.reason("links_capped")
        ff.routes = ff.routes[:max(0, room_r)]
        ff.links = ff.links[:max(0, room_l)]
        self.route_count += len(ff.routes)
        self.link_count += len(ff.links)
        if ff.use_client or ff.use_server or ff.baas or ff.baas_call or ff.browser_client or ff.routes or ff.links \
                or ff.py_server or ff.node_server or ext in NATIVE_EXTS:
            self.files.append(ff)


def _pnpm_globs(text):
    out = []
    inside = False
    for i, line in enumerate(text.split("\n")):
        if i >= 500:
            break
        if re.match(r"^packages\s*:", line):
            inside = True
            continue
        if inside:
            if line and not line[0].isspace() and not line.startswith("-"):
                break
            m = WORKSPACE_LINE_RE.match(line)
            if m:
                out.append(m.group(1))
    return out


def _segs(path):
    return [s for s in path.strip().strip("/").split("/") if s and s != "."]


def _glob_match(glob, rel_dir):
    """Workspace glob against a folder path, one segment at a time: ** matches any number of folders, other
    segments use fnmatch (linear in python 3.9+). Bounded by MAX_PATH_SEGS on both sides."""
    g = []
    for s in _segs(glob):
        if not (s == "**" and g and g[-1] == "**"):
            g.append(s)
    p = _segs(rel_dir)
    if len(g) > MAX_PATH_SEGS or len(p) > MAX_PATH_SEGS:
        return False
    memo = {}

    def go(i, j):
        key = (i, j)
        if key not in memo:
            if i == len(g):
                memo[key] = j == len(p)
            elif g[i] == "**":
                memo[key] = go(i + 1, j) or (j < len(p) and go(i, j + 1))
            else:
                memo[key] = j < len(p) and fnmatch.fnmatchcase(p[j], g[i]) and go(i + 1, j + 1)
        return memo[key]
    return go(0, 0)


def _route_segs(path):
    """A route as a list of ('fixed', name) | ('one',) | ('rest',) | ('opt-rest',) segments, or None."""
    out = []
    for s in _segs(path):
        if s.startswith("[[...") and s.endswith("]]"):
            out.append(("opt-rest",))
        elif s.startswith("[...") and s.endswith("]"):
            out.append(("rest",))
        elif (s.startswith("[") and s.endswith("]")) or s.startswith(":") or (s.startswith("{") and s.endswith("}")):
            out.append(("one",))
        elif s == "*":
            out.append(("rest",))
        else:
            out.append(("fixed", s))
    return out if len(out) <= MAX_PATH_SEGS else None


def _route_proves(route):
    """A route links two apps only if it names something: a fixed segment besides 'api'."""
    return any(k[0] == "fixed" and k[1].lower() != "api" for k in route)


def _route_match(route, path):
    """Segment matcher, no regex: 'one' takes one segment, 'rest' one or more, 'opt-rest' any number.
    A called path cut where an id is joined on ('/api/projects/' + id) ends in '/' and also tries one more
    segment."""
    tries = [_segs(path)]
    if path.endswith("/"):
        tries.append(tries[0] + ["x"])
    for p in tries:
        if len(p) > MAX_PATH_SEGS:
            continue
        memo = {}

        def go(i, j):
            key = (i, j)
            if key not in memo:
                if i == len(route):
                    ok = j == len(p)
                else:
                    k = route[i][0]
                    if k == "fixed":
                        ok = j < len(p) and p[j] == route[i][1] and go(i + 1, j + 1)
                    elif k == "one":
                        ok = j < len(p) and go(i + 1, j + 1)
                    else:
                        ok = (k == "opt-rest" and go(i + 1, j)) or (j < len(p) and (go(i + 1, j + 1) or go(i, j + 1)))
                memo[key] = ok
            return memo[key]
        if go(0, 0):
            return True
    return False


def _file_route(parts):
    """The URL path a file serves by its place in the tree (Next app/ route files, pages/api), else None."""
    name = parts[-1]
    low = [p.lower() for p in parts]
    if ROUTE_FILE_RE.match(name) and "app" in low[:-1]:
        i = len(low) - 2 - low[:-1][::-1].index("app")
        segs = [p for p in parts[i + 1:-1] if not (p.startswith("(") and p.endswith(")")) and not p.startswith("@")]
        return ("file", "/" + "/".join(segs))
    for i in range(len(low) - 2):
        if low[i] == "pages" and low[i + 1] == "api":
            stem = os.path.splitext(name)[0]
            segs = list(parts[i + 1:-1]) + ([] if stem == "index" else [stem])
            return ("file", "/" + "/".join(segs))
    return None


def _server_path(ff):
    low = [p.lower() for p in ff.parts]
    if any(p in SERVER_SEGMENTS for p in low[:-1]) or SERVER_NAME_RE.search(low[-1]):
        return True
    return ff.use_server or bool(ff.routes) or ff.node_server or ff.ext not in JS_EXTS


def _under(parts, folder):
    return tuple(parts[:len(folder)]) == tuple(folder)


def _deps(manifest, keys=("dependencies", "devDependencies", "peerDependencies")):
    out = set()
    for key in keys:
        v = manifest.get(key)
        if isinstance(v, dict):
            out.update(k for k in v if isinstance(k, str))
    return out


def _late(state):
    """Past the short budget for the work after the walk. It starts when the walk ends, so a walk that used
    its whole time limit still has its findings reported (partial), and the total stays under the host's
    limit for one command."""
    if time.monotonic() - state.post_walk_started > POST_WALK_BUDGET_S:
        state.reason("deadline_hit")
        return True
    return False


def arch_findings(state):
    """Turn the walk's records into shape signals, facts, the advice id and flagged decisions.
    Every loop is linear in files (or capped), and checks the walk's deadline."""
    roots = set(state.manifests)
    if state.workspace_globs:
        globs = [g.strip() for g in state.workspace_globs[:MAX_GLOBS] if len(g) <= MAX_GLOB_CHARS]
        inc = [g for g in globs if not g.startswith("!")]
        exc = [g[1:] for g in globs if g.startswith("!")]
        kept = set()
        for r in roots:
            if _late(state):
                break
            rd = "/".join(r)
            if not r or (any(_glob_match(g, rd) for g in inc) and not any(_glob_match(g, rd) for g in exc)):
                kept.add(r)
        roots = kept
    roots.add(())
    deps = {r: _deps(state.manifests.get(r, {})) for r in roots}
    runtime = {r: _deps(state.manifests.get(r, {}), ("dependencies",)) for r in roots}

    def deepest(d, folders):
        for k in range(len(d), -1, -1):
            if tuple(d[:k]) in folders:
                return tuple(d[:k])
        return None

    def root_of(parts):
        return deepest(parts[:-1], roots) or ()

    def wrapped(r):
        return r in state.wrapper_dirs or any(x.startswith("cordova") or x.startswith("@capacitor/")
                                              or x == "@tauri-apps/api" for x in deps[r])

    mobile_roots = {r for r in roots if (deps[r] & MOBILE_DEPS or r in state.expo_dirs or r in state.flutter_dirs)
                    and not wrapped(r)}
    for d in state.flutter_dirs | state.expo_dirs:
        if d not in roots and not wrapped(root_of(d + ("x",))):
            mobile_roots.add(d)
    native = []
    for d in state.native_dirs:
        if d not in state.native_marked:
            continue  # an icon or asset folder, not an Xcode or Gradle project
        r = root_of(d + ("x",))
        if r in mobile_roots or wrapped(r) or any(_under(d, m) for m in mobile_roots):
            continue
        native.append(d)
    web_roots = {r for r in roots if r not in mobile_roots
                 and (deps[r] & WEB_FRAMEWORK_DEPS or runtime[r] & WEB_RUNTIME_DEPS)
                 and not ((deps[r] & NOT_FRONTEND_DEPS or any(x.startswith("@storybook/") for x in deps[r]))
                          and not any(x in BAAS_DEPS for x in deps[r]))}
    apps = [(m, "mobile-app") for m in sorted(mobile_roots)] + [(n, "mobile-app") for n in sorted(native)]
    if len(web_roots) >= 2:
        apps += [(w, "web-app") for w in sorted(web_roots)]
    if len(apps) > MAX_APPS:
        apps = apps[:MAX_APPS]
        state.reason("apps_capped")
    app_folders = {f for f, _ in apps}
    owner = {}  # file rel -> owning app folder or None (files outside every app)
    for ff in state.files:
        owner[ff.rel] = deepest(ff.parts[:-1], app_folders)

    def browser_root(r):
        return r in mobile_roots or (bool(deps[r] & BROWSER_DEPS) and not deps[r] & SERVER_RENDER_DEPS)

    shape = {s: [] for s in SIGNALS}
    facts = {f: [] for f in FACTS}
    routes = []  # (owner folder, route segments, proves)
    for ff in state.files:
        if _late(state):
            break
        for _, path in ff.routes:
            segs = _route_segs(path)
            if segs is not None:
                routes.append((owner[ff.rel], segs, _route_proves(segs)))
            if API_KEYS_RE.search(path):
                facts["api-key-routes"].append(ff.rel)
        if ff.routes:
            shape["own-api-routes"].append(ff.rel)
        if ff.use_server:
            shape["server-actions"].append(ff.rel)
        low = [p.lower() for p in ff.parts]
        if ff.py_server and (low[0] in BACKEND_DIRS or (len(low) > 2 and low[0] in ("apps", "packages") and low[1] in BACKEND_DIRS)):
            shape["separate-backend"].append(ff.rel)
        # The browser reads or writes the database: a real data call, in a file that runs in the browser
        # (it says so, or its app is a browser-only stack such as Vite or Expo), outside server folders.
        if ff.ext in JS_EXTS and ff.baas_call and not _server_path(ff):
            if ff.use_client or ff.browser_client or ff.ext in COMPONENT_EXTS or browser_root(root_of(ff.parts)):
                shape["baas-from-browser"].append(ff.rel)
    for r in sorted(roots):
        if not r:
            continue
        low = [p.lower() for p in r]
        if (low[0] in BACKEND_DIRS and len(low) == 1) or (len(low) == 2 and low[0] in ("apps", "packages") and low[1] in BACKEND_DIRS):
            if deps[r] & NODE_SERVER_DEPS:
                rel = safe_rel(list(r) + ["package.json"])
                if rel:
                    shape["separate-backend"].append(rel)

    # Which database packages each app uses, and which the rest of the repo uses (files and manifests).
    fam_by_owner = {}
    for ff in state.files:
        fam_by_owner.setdefault(owner[ff.rel], set()).update(ff.baas)
    for r in roots:
        fam = {BAAS_DEPS[x] for x in deps[r] if x in BAAS_DEPS}
        if fam:
            fam_by_owner.setdefault(r if r in app_folders else deepest(r, app_folders), set()).update(fam)
    own_files = {}
    for ff in state.files:
        own_files.setdefault(owner[ff.rel], []).append(ff)

    linked = {}
    for folder, kind in apps:
        if _late(state):
            break
        own = own_files.get(folder, [])
        fam = fam_by_owner.get(folder, set())
        other_fam = set()
        for o, f in fam_by_owner.items():
            if o != folder:
                other_fam |= f
        evidence = None
        if fam & other_fam:
            evidence = next((ff.rel for ff in own if ff.baas & other_fam), None)
            if evidence is None and folder in state.manifests:
                evidence = safe_rel(list(folder) + ["package.json"])
        if evidence is None:
            mine = [segs for o, segs, _ in routes if o == folder]
            theirs = [segs for o, segs, proves in routes if o != folder and proves]
            for ff in own:
                if any(any(_route_match(t, p) for t in theirs) and not any(_route_match(m, p) for m in mine)
                       for p in ff.links):
                    evidence = ff.rel
                    break
        if evidence is not None:
            linked[folder] = kind
            shape["second-client"].append(evidence)
        elif kind == "mobile-app" and folder:  # a repo that is one phone app is not 'a phone app in this folder'
            if folder in state.manifests:
                rel = safe_rel(list(folder) + ["package.json"])
            else:
                rel = next((ff.rel for ff in own), None)
            if rel:
                facts["mobile-app"].append(rel)
    if len(web_roots) >= 2 and not any(k == "web-app" for k in linked.values()):
        for w in sorted(web_roots):
            rel = safe_rel(list(w) + ["package.json"]) if w in state.manifests else None
            if rel:
                facts["multi-frontend"].append(rel)

    # Census decisions (strong, not in a comment) inside a linked second app. In a second web app only a
    # client file counts: 'use client' or a browser database call, never its server files.
    client_files = set(shape["baas-from-browser"]) | {ff.rel for ff in state.files if ff.use_client}
    flagged = []
    linked_folders = set(linked)
    for t in TYPES:
        for rank, path, line_no, pid in sorted(state.hits[t]):
            if rank != 0 or pid.endswith("-comment"):
                continue
            app = deepest(tuple(path.split("/"))[:-1], app_folders)
            if app is None or app not in linked_folders:
                continue
            kind = linked[app]
            if kind == "web-app" and path not in client_files:
                continue
            flagged.append({"kind": "decision-in-client-app", "type": t, "path": path, "line": line_no, "app": kind})
    for k in shape:
        shape[k] = sorted(set(shape[k]))
    for k in facts:
        facts[k] = sorted(set(facts[k]))
    if shape["second-client"]:
        advice = "shared-api"
    elif shape["own-api-routes"] or shape["server-actions"] or shape["separate-backend"]:
        advice = "each-entry-checks"
    elif any(shape.values()):
        advice = "one-server-place"
    else:
        advice = None
    return shape, facts, advice, flagged


def build_architecture(state):
    state.post_walk_started = time.monotonic()
    shape, facts, advice, flagged = arch_findings(state)
    shape_l = {k: v[:MAX_PER_SIGNAL] for k, v in shape.items()}
    facts_l = {k: v[:MAX_PER_SIGNAL] for k, v in facts.items()}
    flagged_l = flagged[:MAX_PER_SIGNAL]

    def render():
        reasons = list(state.reasons)
        found = any(shape.values()) or any(facts.values())
        coverage = "complete" if not reasons else ("partial" if found else "not_determined")
        return {
            "ok": True,
            "section": "architecture",
            "partial": bool(reasons),
            "version": __version__,
            "coverage": coverage,
            "partial_reasons": reasons,
            "stats": dict(state.stats, files_read=state.files_read),
            "shape": [{"signal": k, "path": p} for k in SIGNALS for p in shape_l[k]],
            "facts": [{"fact": k, "path": p} for k in FACTS for p in facts_l[k]],
            "advice": advice,
            "candidates": flagged_l,
            "totals": {
                "shape": {k: {"listed": len(shape_l[k]), "not_listed": len(shape[k]) - len(shape_l[k])} for k in SIGNALS},
                "facts": {k: {"listed": len(facts_l[k]), "not_listed": len(facts[k]) - len(facts_l[k])} for k in FACTS},
                "candidates": {"listed": len(flagged_l), "not_listed": len(flagged) - len(flagged_l)},
            },
        }

    result = render()
    while len(dumps(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        lists = [shape_l[k] for k in SIGNALS] + [facts_l[k] for k in FACTS] + [flagged_l]
        biggest = max(lists, key=len)
        if not biggest:
            break
        biggest.pop()
        state.reason("output_trimmed")
        result = render()
    return result


# ------------------------------------------------------------------ section: payment state
#
# `--section payment` runs its own walk too (an ArchState, so it can tell which files run in the browser
# by the same rule as the architecture section). It lists, from the files only, never confirmed by reading:
# places that save whether someone has paid; Stripe payment handlers and whether a signature check is found
# in the handler, the files it imports, or the files that import it (not-found only when all of those were
# read; anything this run cannot follow is unresolved); prices written in the app beside
# payment-company price ids; and screens that save money or paid fields straight to the database.

PAY_WHERE = ("webhook", "success-page", "page", "browser", "other")
SIGNATURE = ("found", "not-found", "unresolved")
PAID_FIELDS = ("is_paid", "paid", "has_paid", "subscription_status", "status", "plan", "tier", "is_pro",
               "is_premium", "credits")
PAID_TABLES = ("subscriptions", "payments", "purchases", "entitlements", "invoices")
CLIENT_FIELDS = ("credits", "plan", "tier", "is_paid", "paid", "balance", "price", "total", "amount")
CLIENT_MONEY = ("balance", "price", "total", "amount")  # listed only beside order or payment words
MAX_PAY_LIST = 25
MAX_PRICE_PAIR = 3
WRITE_WINDOW = 3  # a field counts on the write call's line or the 3 lines after it
MAX_HOOK_DEPTH = 3  # import levels followed from a payment handler
MAX_HOOK_FILES = 20  # files followed per handler; past it the verdict is unresolved
MAX_IMPORTERS = 10  # files that import the handler, followed up to MAX_HOOK_DEPTH levels

WRITE_CALL_RE = re.compile(r"\.\s*(?:update|insert|upsert|create|updateMany|createMany|upsertMany)\s*\(|"
                           r"\b(?:updateDoc|setDoc|addDoc)\s*\(|\bupdate\s+[\w.\"`]+\s+set\b", re.I)
FIELD_KEY_RE = re.compile(r"""(?<![\w$.])['"]?([A-Za-z_$][\w$]*)['"]?\s*:(?!:)""")
FIELD_EQ_RE = re.compile(r"""(?<![\w$.])([A-Za-z_$][\w$]*)\s*=(?![=>])""")  # keyword arguments, SQL SET
FROM_TABLE_RE = re.compile(r"""\bfrom\s*\(\s*['"`]([\w.-]+)['"`]\s*\)""")
SQL_TABLE_RE = re.compile(r"""^update\s+[\"`]?(?:\w+\.)?(\w+)""", re.I)
PAID_TABLE_RE = re.compile(r"^(?:subscriptions?|payments?|purchases?|entitlements?|invoices?)$", re.I)
PAY_WORDS = r"subscri|payment|billing|invoice|stripe|checkout"
STATUS_CONTEXT_RE = re.compile(PAY_WORDS + r"|['\"](?:paid|trialing|past_due|unpaid)['\"]", re.I)
PLAN_CONTEXT_RE = re.compile(PAY_WORDS + r"|price|['\"](?:free|pro|premium|basic|starter|plus|team|enterprise|"
                             r"business|hobby|growth|scale|gold|silver|platinum|bronze|lifetime|monthly|yearly|annual)['\"]", re.I)
MONEY_CONTEXT_RE = re.compile(PAY_WORDS + r"|order|purchase|transaction|cart|charge", re.I)
PRICE_ID_VALUE_RE = re.compile(r"price_?id|['\"`]price_[A-Za-z0-9]", re.I)
PAYMENT_EVENT_RE = next(rx for pid, _, rx, _ in PATTERNS["paid"] if pid == "payment-event")
STRIPE_SIG_RE = re.compile(r"""['"]stripe-signature['"]""", re.I)
VERIFY_RE = re.compile(r"\b(?:constructEvent(?:Async)?|construct_event|verifyHeader|verify_header|timingSafeEqual|"
                       r"compare_digest)\s*\(|\bcrypto\.subtle\.verify\s*\(|\bwebhooks\s*\.\s*unmarshal\s*\(")
HMAC_RE = re.compile(r"\bcreateHmac\s*\(|\bhmac\.new\s*\(|\bcrypto\.subtle\.sign\s*\(")
SIG_COMPARE_RE = re.compile(r"(?:[=!]==?).{0,80}\bsig|\bsig\w*\b.{0,80}(?:[=!]==?)", re.I)
ENTRY_RE = re.compile(r"\bexport\s+default\b|\bmodule\.exports\b|\bexports\.(?:handler|default)\b|"
                      r"\bexport\s+(?:async\s+)?function\s+(?:handler|GET|POST|PUT|PATCH|DELETE)\b|"
                      r"\bexport\s+const\s+(?:handler|GET|POST|PUT|PATCH|DELETE)\b|\bDeno\.serve\s*\(|^\s*serve\s*\(|"
                      r"\bclass\s+handler\b|\bdef\s+handler\s*\(|=\s*(?:Flask|FastAPI)\s*\(")
JS_IMPORT_RE = re.compile(r"""(?:\bfrom\s*|\brequire\(\s*|\bimport\(\s*|^\s*import\s+)['"]([^'"\s]+)['"]""")
PY_FROM_RE = re.compile(r"^\s*from\s+(\.*)(\w[\w.]*)?\s+import\b\s*\(?\s*([\w, ]*)")
PY_IMPORT_RE = re.compile(r"^\s*import\s+(\w[\w., ]*)")
PY_NAME_RE = re.compile(r"\w+")
SUCCESS_SEG_RE = re.compile(r"(?:^|[-_.])(?:success|thank-?you|thanks|confirm(?:ation)?)(?:$|[-_.])", re.I)
FUNCTION_DIRS = (("supabase", "functions"), ("netlify", "functions"))
RESOLVE_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
EXTERNAL_PREFIXES = ("node:", "http:", "https:", "npm:", "jsr:", "data:", "bun:", "virtual:")
NODE_BUILTINS = frozenset((
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto", "dgram", "dns",
    "domain", "events", "fs", "http", "http2", "https", "inspector", "module", "net", "os", "path", "perf_hooks",
    "process", "punycode", "querystring", "readline", "repl", "stream", "string_decoder", "timers", "tls", "tty",
    "url", "util", "v8", "vm", "worker_threads", "zlib"))
LOCAL_DEP_PREFIXES = ("workspace:", "file:", "link:", "portal:")


def _snake(name):
    return CAMEL_SPLIT_RE.sub("_", name).lower().strip("$")


class PayFacts:
    __slots__ = ("writers", "client_writes", "event_line", "entry_mark")

    def __init__(self):
        self.writers = []  # (line, field)
        self.client_writes = []  # (line, field)
        self.event_line = None
        self.entry_mark = False


class _Blocks:
    """Block-comment state across the lines of one JS-like file."""
    __slots__ = ("block", "tmpl")

    def __init__(self):
        self.block = self.tmpl = False


def _cut_blocks(line, st):
    """The line with /* ... */ spans cut out. Quotes are tracked so '/*' in a string (a glob) is kept."""
    if not st.block and not st.tmpl and "/*" not in line and "`" not in line:
        return line
    out = []
    q = "`" if st.tmpl else None
    i, n = 0, len(line)
    while i < n:
        if st.block:
            j = line.find("*/", i)
            if j < 0:
                break
            st.block = False
            i = j + 2
            continue
        ch = line[i]
        if q:
            out.append(ch)
            if ch == "\\":
                out.append(line[i + 1:i + 2])
                i += 2
                continue
            if ch == q:
                q = None
            i += 1
            continue
        if ch in "'\"`":
            q = ch
        elif line.startswith("//", i):
            out.append(line[i:])
            break
        elif line.startswith("/*", i):
            st.block = True
            i += 2
            continue
        out.append(ch)
        i += 1
    st.tmpl = q == "`"
    return "".join(out)


def _receiver(prefix):
    """The name chain a call is made on (`supabase.from('x')` in `supabase.from('x').update(`)."""
    i, depth = len(prefix), 0
    while i > 0:
        ch = prefix[i - 1]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and not (ch.isalnum() or ch in "_$.?!'\"`-"):
            break
        i -= 1
    return prefix[i:]


class PayState(ArchState):
    """An architecture walk that also records payment facts and imports per file."""

    def __init__(self, opts):
        ArchState.__init__(self, opts)
        self.pay = {}  # rel -> PayFacts
        self.imports = {}  # rel -> [("js", spec) | ("py", dots, module, names)]
        self.verified_files = set()
        self.scanned = set()  # files whose lines were read
        self.known = set()  # every file the walk saw
        self.dirs = set()

    def on_dir(self, parts):
        ArchState.on_dir(self, parts)
        self.dirs.add("/".join(parts))

    def on_meta(self, path, parts, lower, is_link):
        self.known.add("/".join(parts))
        return ArchState.on_meta(self, path, parts, lower, is_link)

    def on_lines(self, parts, ext, lines):
        ArchState.on_lines(self, parts, ext, lines)
        rel = safe_rel(parts)
        if rel is None or _not_app(parts[:-1]):
            return
        self.scanned.add(rel)
        pf = PayFacts()
        imports = []
        code = []  # per line: code text without comments, or None for a comment or blank line
        blocks = _Blocks() if ext in JS_EXTS else None
        for i, line in enumerate(lines):
            if (i % DEADLINE_LINE_TICK == 0 or len(line) > 512) and self.over_deadline():
                break
            if line.endswith("\r"):
                line = line[:-1]
            if len(line) > LINE_CLIP_CHARS:
                line = line[:LINE_CLIP_CHARS]
            if blocks is not None:
                line = _cut_blocks(line, blocks)
            stripped = line.strip()
            code.append(None if (not stripped or comment_body(stripped, ext) is not None)
                        else strip_trailing_comment(line, ext))
        strong = hmac = compared = False
        for i, c in enumerate(code):
            if c is None:
                continue
            if (i % DEADLINE_LINE_TICK == 0 or len(c) > 512) and self.over_deadline():
                break
            if pf.event_line is None and (PAYMENT_EVENT_RE.search(c) or STRIPE_SIG_RE.search(c)):
                pf.event_line = i + 1
            if not pf.entry_mark and ENTRY_RE.search(c):
                pf.entry_mark = True
            strong = strong or VERIFY_RE.search(c) is not None
            hmac = hmac or HMAC_RE.search(c) is not None
            compared = compared or SIG_COMPARE_RE.search(c) is not None
            if ext == ".py":
                m = PY_FROM_RE.match(c)
                if m:
                    names = PY_NAME_RE.findall(m.group(3))
                    if not names and c.rstrip().endswith("("):
                        nxt = next((x for x in code[i + 1:i + 3] if x is not None), "")
                        names = PY_NAME_RE.findall(nxt)
                    imports.append(("py", len(m.group(1)), m.group(2) or "", names))
                else:
                    m = PY_IMPORT_RE.match(c)
                    if m:
                        for mod in m.group(1).split(","):
                            mod = mod.split(" as ")[0].strip()
                            if mod:
                                imports.append(("py", 0, mod, []))
            elif ext in JS_EXTS:
                for m in JS_IMPORT_RE.finditer(c):
                    imports.append(("js", m.group(1)))
            for m in WRITE_CALL_RE.finditer(c):
                head = c[m.start():]
                sql = m.group(0).lower().startswith("update")
                prefix = c[:m.start()]
                recv = "" if sql else _receiver(prefix)
                if not sql and not prefix.strip() and i > 0 and code[i - 1] is not None:
                    recv = _receiver(code[i - 1].rstrip())  # a chain split over lines
                if "stripe" in recv.lower():
                    continue  # a call to the payment company, not a database write
                window = [head]
                depth = head.count("(") - head.count(")")
                for x in code[i + 1:i + WRITE_WINDOW + 1]:
                    if not sql and depth <= 0:
                        break  # the call's brackets closed: later lines are another statement
                    if x is not None:
                        window.append(x)
                        depth += x.count("(") - x.count(")")
                text = " ".join(window)
                before = " ".join(code[j] for j in range(max(0, i - 2), i) if code[j] is not None) + " " + prefix
                if "checkout_sessions" in before or "checkout_sessions" in text:
                    break  # a payment-company extension's checkout request, not a saved paid state
                keys = _fields(text, text if sql else head)
                context = prefix + " " + text
                field = _paid_field(keys, context) or _paid_table(before, recv, head if sql else "")
                if field:
                    pf.writers.append((i + 1, field))
                cf = _client_field(keys, context + " " + before, text)
                if cf:
                    pf.client_writes.append((i + 1, cf))
                break
        if strong or (hmac and compared):
            self.verified_files.add(rel)
        if imports:
            self.imports[rel] = imports
        if pf.writers or pf.client_writes or pf.event_line:
            self.pay[rel] = pf


def _fields(text, eq_text):
    """Field names written: object keys anywhere in the window; name = value only on the call's own line
    (keyword arguments) or anywhere in a SQL UPDATE ... SET."""
    found = [(m.start(), _snake(m.group(1))) for m in FIELD_KEY_RE.finditer(text)]
    found += [(m.start(), _snake(m.group(1))) for m in FIELD_EQ_RE.finditer(eq_text)]
    return [f for _, f in sorted(found)]


def _paid_field(keys, context):
    for f in keys:
        if f not in PAID_FIELDS:
            continue
        if f == "status" and not STATUS_CONTEXT_RE.search(context):
            continue
        if f in ("plan", "tier") and not PLAN_CONTEXT_RE.search(context):
            continue
        return f
    return None


def _paid_table(before, recv, sql_head):
    """The table the write goes to, when it is a payment table: the nearest .from('x') before the call,
    the model a call is made on (prisma.subscription.update), or the table of a SQL UPDATE."""
    word = None
    if sql_head:
        m = SQL_TABLE_RE.match(sql_head)
        word = m.group(1) if m else None
    else:
        tables = FROM_TABLE_RE.findall(before)
        if tables:
            word = tables[-1]
        elif "." in recv and "(" not in recv:
            word = recv.rsplit(".", 1)[1]
    if word and PAID_TABLE_RE.match(word):
        word = word.lower()
        return word if word.endswith("s") else word + "s"
    return None


def _client_field(keys, context, text):
    for f in keys:
        if f not in CLIENT_FIELDS:
            continue
        if f in ("plan", "tier") and not PLAN_CONTEXT_RE.search(context):
            continue
        if f in CLIENT_MONEY and (not MONEY_CONTEXT_RE.search(context) or PRICE_ID_VALUE_RE.search(text)):
            continue
        return f
    return None


def _norm(parts):
    out = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if not out:
                return None
            out.pop()
        else:
            out.append(p)
    return out


def _js_candidates(segs):
    stem = "/".join(segs)
    cands = [stem] + [stem + e for e in RESOLVE_EXTS] + [stem + "/index" + e for e in RESOLVE_EXTS]
    base, ext = os.path.splitext(stem)
    if ext in (".js", ".jsx", ".mjs", ".cjs"):
        cands += [base + e for e in RESOLVE_EXTS]  # ESM style: './x.js' written for x.ts
    return cands


class _Resolver:
    """Places each import of a scanned file: a file this run read, outside code, or unknown."""

    def __init__(self, state):
        self.state = state
        self.deps = set()
        self.local_pkgs = set()
        self.pkg_roots = []
        for d, man in state.manifests.items():
            self.pkg_roots.append(list(d))
            name = man.get("name")
            if isinstance(name, str):
                self.local_pkgs.add(name)
            for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                v = man.get(key)
                if not isinstance(v, dict):
                    continue
                for k, ver in v.items():
                    if not isinstance(k, str):
                        continue
                    if isinstance(ver, str) and ver.startswith(LOCAL_DEP_PREFIXES):
                        self.local_pkgs.add(k)
                    else:
                        self.deps.add(k)
        self.cache = {}

    def edges(self, rel):
        """(files this run read that rel imports, True when an import could not be placed)."""
        if rel in self.cache:
            return self.cache[rel]
        parts = rel.split("/")
        found, unknown = set(), False
        for imp in self.state.imports.get(rel, ()):
            got = self._js(parts, imp[1]) if imp[0] == "js" else self._py(parts, imp[1], imp[2], imp[3])
            if got is None:
                continue  # outside code
            hit = [c for c in got if c in self.state.scanned]
            if hit:
                found.add(hit[0])
            else:
                unknown = True
        self.cache[rel] = (found, unknown)
        return self.cache[rel]

    def _roots(self, parts):
        """Folders a non-relative import may start from: the repo root, the nearest package folder, and src/ of each."""
        roots = [[]]
        best = None
        for r in self.pkg_roots:
            if r and tuple(parts[:len(r)]) == tuple(r) and (best is None or len(r) > len(best)):
                best = r
        if best:
            roots.append(best)
        return roots + [r + ["src"] for r in roots]

    def _js(self, parts, spec):
        """Candidate paths, or None for outside code."""
        if spec.startswith(EXTERNAL_PREFIXES):
            return None
        ext = os.path.splitext(spec.split("?")[0])[1].lower()
        if ext and ext not in RESOLVE_EXTS and ext not in (".js", ".jsx", ".mjs", ".cjs"):
            if ext.lstrip(".").isalnum() and len(ext) <= 6:
                return None  # a stylesheet, image or data file: it cannot check a signature
        if spec.startswith(("./", "../")) or spec in (".", ".."):
            segs = _norm(list(parts[:-1]) + spec.split("/"))
            return [] if segs is None else _js_candidates(segs)
        segs = spec.split("/")
        pkg = "/".join(segs[:2]) if spec.startswith("@") and len(segs) > 1 else segs[0]
        if segs[0] in NODE_BUILTINS:
            return None
        if pkg in self.local_pkgs:
            return []  # the repo's own workspace package: not followed
        if pkg in self.deps:
            return None
        stems = []
        if spec[0] in "@~#$":
            stems.append(spec[1:].lstrip("/").split("/"))  # @lib/x -> lib/x, $lib/x -> lib/x, @/x -> x
            if len(segs) > 1:
                stems.append(segs[1:])  # @lib/x -> x
        else:
            stems.append(segs)
        out = []
        for root in self._roots(parts):
            for st in stems:
                segs2 = _norm(root + st)
                if segs2:
                    out += _js_candidates(segs2)
        return out

    def _py(self, parts, dots, mod, names):
        mod_segs = mod.split(".") if mod else []
        if dots:
            base = list(parts[:-1])
            for _ in range(dots - 1):
                if not base:
                    return []
                base.pop()
            bases = [base]
        else:
            top = mod_segs[0] if mod_segs else ""
            d = list(parts[:-1])
            ancestors = [d[:k] for k in range(len(d), -1, -1)]
            bases = []
            for b in ancestors + [["src"]]:
                p = "/".join(b + [top])
                if p in self.state.dirs or p + ".py" in self.state.known:
                    bases.append(b)
            if not bases:
                return None  # not a module in this repo: the standard library or an installed package
        out = []
        for b in bases:
            stem = "/".join(b + mod_segs)
            if mod_segs:
                out += [stem + ".py", stem + "/__init__.py"]
            for n in names:
                sub = (stem + "/" if stem else "") + n
                out += [sub + ".py", sub + "/__init__.py"]
        return out


def _closure(start, depth, res, cap):
    """Files reached from start by imports, up to depth levels. Complete is False when an import could not be
    placed, or a level or the file cap stopped the walk with files still to read."""
    seen = {start}
    frontier = [start]
    complete = True
    for level in range(depth + 1):
        nxt = []
        for f in frontier:
            targets, unknown = res.edges(f)
            if unknown:
                complete = False
            for t in sorted(targets):
                if t in seen:
                    continue
                if level == depth or len(seen) >= cap:
                    complete = False
                    continue
                seen.add(t)
                nxt.append(t)
        frontier = nxt
    return seen, complete


def _signature(rel, state, res, importers):
    """found: a check in the handler, a file it imports (3 levels), or a file importing it with what that file
    imports. not-found: every one of those files was read and none checks. unresolved: anything else."""
    verified = state.verified_files
    seen, complete = _closure(rel, MAX_HOOK_DEPTH, res, MAX_HOOK_FILES)
    if seen & verified:
        return "found"
    ups, frontier = set(), [rel]
    for _ in range(MAX_HOOK_DEPTH):
        nxt = []
        for f in frontier:
            for u in sorted(importers().get(f, ())):
                if u not in ups and u != rel:
                    if len(ups) >= MAX_IMPORTERS:
                        complete = False
                        continue
                    ups.add(u)
                    nxt.append(u)
        frontier = nxt
    if frontier:
        if any(importers().get(f) for f in frontier):
            complete = False  # more levels of importers than are followed
    for u in sorted(ups):
        got, ok = _closure(u, MAX_HOOK_DEPTH - 1, res, MAX_HOOK_FILES)
        if got & verified:
            return "found"
        complete = complete and ok
    return "not-found" if complete else "unresolved"


def _entry_point(ff_routes, ff_server, parts, pf):
    low = [p.lower() for p in parts]
    if _file_route(parts) is not None:
        return True
    for a, b in FUNCTION_DIRS:
        for k in range(len(low) - 1):
            if low[k] == a and low[k + 1] == b:
                below = low[k + 2:]
                return (0 < len(below) <= 2 and not any(x.startswith("_") for x in below) and pf.entry_mark)
    if len(low) > 1 and low[0] == "api":
        return not any(x.startswith("_") for x in low[1:]) and pf.entry_mark
    return bool(ff_routes) and ff_server


def _page_kind(parts):
    low = [p.lower() for p in parts]
    stem = os.path.splitext(low[-1])[0]
    if any(SUCCESS_SEG_RE.search(s) for s in low[:-1]) or SUCCESS_SEG_RE.search(stem):
        return "success-page"
    for k in range(len(low) - 1):
        if low[k] == "checkout" and low[k + 1] == "return":
            return "success-page"
    if "app" in low[:-1] and stem == "page":
        return "page"
    if "pages" in low[:-1]:
        i = low.index("pages")
        if i + 1 < len(low) - 1 and low[i + 1] == "api":
            return None
        return "page"
    return None


def pay_findings(state):
    state.post_walk_started = time.monotonic()
    shape, _, _, _ = arch_findings(state)
    browser = set(shape["baas-from-browser"])
    ff_by_rel = {ff.rel: ff for ff in state.files}
    res = _Resolver(state)
    reverse = []

    def importers():
        if not reverse:
            rev = {}
            for f in sorted(state.imports):
                if _late(state):
                    break
                for t in res.edges(f)[0]:
                    rev.setdefault(t, set()).add(f)
            reverse.append(rev)
        return reverse[0]

    writers, hooks, client = [], [], []
    for rel in sorted(state.pay):
        if _late(state):
            break
        pf = state.pay[rel]
        parts = rel.split("/")
        ff = ff_by_rel.get(rel)
        is_entry = _entry_point(ff.routes if ff else [], bool(ff and (ff.node_server or ff.py_server)), parts, pf)
        is_hook = is_entry and pf.event_line is not None
        if is_hook:
            sig = "found" if rel in state.verified_files else _signature(rel, state, res, importers)
            if sig != "found" and state.stopped:
                sig = "unresolved"  # the walk stopped early: the check may sit in a file it never reached
            hooks.append({"path": rel, "line": pf.event_line, "signature": sig})
            where = "webhook"
        else:
            where = _page_kind(parts)
            if where != "success-page" and rel in browser:
                where = "browser"
            where = where or "other"
        for line_no, field in pf.writers:
            writers.append({"path": rel, "line": line_no, "field": field, "where": where})
        if rel in browser:
            for line_no, field in pf.client_writes:
                client.append({"path": rel, "line": line_no, "field": field})
    consts, ids = [], []
    for rank, path, line_no, pid in sorted(state.hits["price"], key=lambda h: (h[1], h[2])):
        if pid in ("price-constant", "price-table"):
            consts.append({"path": path, "line": line_no})
        elif pid == "billing-price-id":
            ids.append({"path": path, "line": line_no})
    if not (consts and ids):
        consts, ids = [], []
    return writers, hooks, {"constants": _first_per_file(consts), "payment_ids": _first_per_file(ids)}, client


def _first_per_file(items):
    out, seen = [], set()
    for it in items:
        if it["path"] not in seen:
            seen.add(it["path"])
            out.append(it)
        if len(out) >= MAX_PRICE_PAIR:
            break
    return out


def build_payment(state):
    writers, hooks, pairs, client = pay_findings(state)
    lists = {"writers": writers, "webhooks": hooks, "client_writes": client}
    shown = {k: v[:MAX_PAY_LIST] for k, v in lists.items()}

    def render():
        reasons = list(state.reasons)
        found = any(lists.values()) or bool(pairs["constants"])
        coverage = "complete" if not reasons else ("partial" if found else "not_determined")
        return {
            "ok": True,
            "section": "payment",
            "partial": bool(reasons),
            "version": __version__,
            "coverage": coverage,
            "partial_reasons": reasons,
            "stats": dict(state.stats, files_read=state.files_read),
            "writers": shown["writers"],
            "webhooks": shown["webhooks"],
            "price_pairs": pairs,
            "client_writes": shown["client_writes"],
            "totals": {k: {"listed": len(shown[k]), "not_listed": len(lists[k]) - len(shown[k])} for k in lists},
        }

    result = render()
    while len(dumps(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        biggest = max(shown.values(), key=len)
        if not biggest:
            break
        biggest.pop()
        state.reason("output_trimmed")
        result = render()
    return result


VOCABULARY = frozenset(VOCABULARY_CENSUS + SECTIONS + SIGNALS + FACTS + ADVICE + COVERAGE + ARCH_KINDS + APP_KINDS
                       + ARCH_REASONS)
PAY_VOCABULARY = VOCABULARY | frozenset(PAY_WHERE + SIGNATURE + PAID_FIELDS + PAID_TABLES + CLIENT_FIELDS)


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
        return dict(result, demo_keys=list(state.demo_keys), demo_keys_trimmed=state.demo_keys_capped)
    while len(dumps(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        biggest = max(reversed(TYPES), key=lambda t: len(candidates[t]))
        if not candidates[biggest]:
            break
        candidates[biggest].pop()
        totals[biggest]["listed"] -= 1
        totals[biggest]["not_listed"] += 1
        state.reason("output_trimmed")
        result = render()
    return add_demo_keys(result, state)


def add_demo_keys(result, state):
    """Add the sample-key places only in the room the findings leave: the findings are trimmed exactly as
    before, then the list shrinks to fit, and with no room at all both fields are left out (the skill then
    reports keys as it always did)."""
    keys = list(state.demo_keys)
    trimmed = state.demo_keys_capped
    while True:
        out = dict(result)
        out["demo_keys"] = keys
        out["demo_keys_trimmed"] = trimmed
        if len(dumps(out).encode("utf-8")) <= MAX_OUTPUT_BYTES:
            return out
        if not keys:
            return result
        keys = keys[:-1]
        trimmed = True


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
    parser.add_argument("--section", choices=SECTIONS)
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
        opts = Options(args.max_files, args.max_file_bytes, args.max_total_bytes, args.deadline_s)
        if args.section == "payment":
            state = PayState(opts)
            walk(repo, state)
            emit(build_payment(state))
            return 0
        if args.section == "architecture":
            state = ArchState(opts)
            walk(repo, state)
            emit(build_architecture(state))
            return 0
        state = State(opts)
        walk(repo, state)
        emit(build(state, args.uncapped))
        return 0
    except UsageError:
        emit(envelope("usage"))
        return 0
    except Exception:  # last resort: never a traceback, never a path, never a message
        try:
            emit(envelope("internal"))
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
