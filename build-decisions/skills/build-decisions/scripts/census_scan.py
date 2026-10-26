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

`--section warnings` prints each job an app does with two or more libraries (several-ways) and the packages
a JavaScript app lists but does not use (unused-parts). Try it:
    cd build-decisions/evals/fixtures && python3 -I ../../skills/build-decisions/scripts/census_scan.py \
        --repo notewell --section warnings | python3 -m json.tool
Tests: python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p "*_test.py"
"""
__version__ = "0.8.0"

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
    "internal-warnings": "The warnings part of the helper hit an unexpected error. The rest of the report is not affected.",
    "internal:shared-missing": "The helper is missing its shared_rules.py file. Update the plugin, then run it again.",
    "internal:shared-broken": "The helper's shared_rules.py file is damaged. Update the plugin, then run it again.",
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
import types

SHARED_EXPORTS = ("NEVER_OPEN_DIRS", "NEVER_OPEN_DIR_PAIRS", "NEVER_OPEN_FILE_RE", "NEVER_OPEN_FILES", "STOPLINE_FIELDS",
                  "stopline_line_terms", "stopline_kind", "stopline_whole_terms")


def load_shared():
    """Load shared_rules.py from next to this file by path (python3 -I keeps this folder off sys.path).
    Returns (module, None) or (None, error code). No .pyc, and nothing on sys.path can stand in."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_rules.py")
    try:
        with open(path, "rb") as fh:
            data = fh.read().replace(b"\r\n", b"\n")
    except FileNotFoundError:
        return None, "internal:shared-missing"
    except OSError:
        return None, "internal:shared-broken"
    module = types.ModuleType("shared_rules")
    module.__file__ = path
    try:
        exec(compile(data, path, "exec"), module.__dict__)
    except Exception:
        return None, "internal:shared-broken"
    if not all(hasattr(module, name) for name in SHARED_EXPORTS):
        return None, "internal:shared-broken"
    return module, None


shared, SHARED_ERROR = load_shared()
if SHARED_ERROR is not None and __name__ == "__main__":
    sys.stdout.write(json.dumps({"ok": False, "error": SHARED_ERROR, "hint": HINTS[SHARED_ERROR], "partial": True},
                                separators=(",", ":")) + "\n")
    sys.exit(0)


# ------------------------------------- walk rules (copied from custody-check 0.3.2, plus 0.3.3's .mts/.cts)

EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "vendor", "venv", ".venv", "__pycache__", "coverage"}
SKIP_BASENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "cargo.lock", "composer.lock", "gemfile.lock"}
SKIP_EXT_SUFFIXES = (".map", ".min.js", ".min.css", ".bundle.js")
CODE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro", ".py", ".rb", ".go", ".java", ".kt", ".php", ".cs", ".swift", ".dart"}
SQL_EXTS = {".sql", ".psql", ".pgsql", ".ddl"}
SCHEMA_EXTS = {".prisma", ".graphql", ".gql"}
SCAN_EXTS = CODE_EXTS | SQL_EXTS | SCHEMA_EXTS
MARKUP_EXTS = {".jsx", ".tsx", ".vue", ".svelte", ".astro"}  # page copy sits outside strings here
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
    r"|xox[baprs]-|xapp-|whsec_|eyJ|-----BEGIN")
LONG_RUN_RE = re.compile(r"[A-Za-z0-9_\-+/=]{20,}")
CRED_URL_RE = re.compile(r"://[^\s/:@'\"`]+:[^\s/@'\"`]+@")  # a password inside a URL
SECRET_VALUE_RE = re.compile(r"(?:pass(?:word|wd)?|pwd|pw|secret|token|api[_-]?key|private[_-]?key)\w*['\"]?\s*[:=]\s*['\"`][^'\"`\s]{4,}", re.I)


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
    """Anything that could be a secret counts: known key shapes, a password in a URL or after a secret-like
    name, and any long run that mixes two kinds of characters (hex secrets included). Unsure means key-like."""
    if OTHER_KEY_RE.search(text) or CRED_URL_RE.search(text) or SECRET_VALUE_RE.search(text):
        return True
    for m in LONG_RUN_RE.finditer(text):
        run = m.group(0)
        kinds = sum(1 for test in (str.islower, str.isupper, str.isdigit) if any(test(c) for c in run))
        if kinds >= 2:
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
VOCABULARY_CENSUS = (TYPES + STRENGTHS + PATTERN_IDS + shared.STOPLINE_FIELDS + WARNINGS + PARTIAL_REASONS
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
        self.hints = []  # (order found, whole word, hint)
        self.hints_capped = False
        self.stopped = False
        self.collect_demo_keys = True  # census only; the section scans turn it off
        self.census_lines = True  # run the census line rules on each file; the warnings walk turns it off
        self.demo_keys = []
        self.demo_keys_capped = False

    def reason(self, r):
        if r not in self.reasons:
            self.reasons.append(r)

    # Hooks for a section scan (ArchState). The census uses none of them, so its line never changes.
    def on_dir(self, parts):
        pass

    def on_excluded(self, parts):
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
    if not state.census_lines:
        return
    is_schema = ext in SQL_EXTS or ext in SCHEMA_EXTS or SCHEMA_NAME_RE.search(parts[-1]) is not None
    found = []
    hints = []
    demo_lines = []
    where_open = 0
    lines_read = len(lines)
    for i, line in enumerate(lines, 1):
        if line.endswith("\r"):
            line = line[:-1]
        clipped = len(line) > LINE_CLIP_CHARS
        if clipped:
            line = line[:LINE_CLIP_CHARS]
        if (i % DEADLINE_LINE_TICK == 0 or len(line) > 512) and state.over_deadline():
            lines_read = i - 1
            break
        if state.collect_demo_keys and not clipped and line_has_only_sample_keys(line):  # a cut line is never listed
            demo_lines.append(i)
        for typ, pid, strength in classify_line(line, ext, where_open > 0):
            found.append((typ, 0 if strength == "strong" else 1, i, pid))
        where_open = 3 if WHERE_OPEN_RE.search(line) else max(0, where_open - 1)
    if is_schema and lines_read:
        # Stop-line fields: the shared matcher, comments and string values left out (shared_rules.py), on the lines
        # the loop above read (main kept those when the deadline came mid-file). One linear pass over a file the
        # size cap already bounds, so it does not stop at the deadline itself.
        last, seen = 0, set()
        src = text if lines_read == len(lines) else "\n".join(lines[:lines_read])
        terms = shared.stopline_line_terms(src, shared.stopline_kind(parts[-1]), clip=LINE_CLIP_CHARS)
        for line_no, ident, field in terms:
            if line_no != last:
                last, seen = line_no, set()
            if field not in seen:
                seen.add(field)
                hints.append((line_no, field, field in shared.stopline_whole_terms(ident)))
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
    for line_no, field, whole in hints:
        # Whole-word and one-word (creditcard) hints are capped apart, so a one-word hint never takes the
        # place of a whole-word one; build() keeps whole-word hints first.
        if sum(1 for h in state.hints if h[1] == whole) >= MAX_STOPLINE_HINTS:
            state.hints_capped = True
            continue
        state.hints.append((len(state.hints), whole, {"path": rel, "line": line_no, "field": field}))


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
                    state.on_excluded(parts + [name])
                    continue
                parent = parts[-1] if parts else ""
                if name in shared.NEVER_OPEN_DIRS or (parent, name) in shared.NEVER_OPEN_DIR_PAIRS:
                    count_never_open(e.path, state)
                    continue
                state.on_dir(parts + [name])
                subdirs.append((e.path, parts + [name]))
                continue
            if name in shared.NEVER_OPEN_FILES or shared.NEVER_OPEN_FILE_RE.match(name):
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

SECTIONS = ("architecture", "payment", "warnings")
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
                 "routes", "links", "node_server", "py_server", "value_score")

    def __init__(self, rel, parts, ext):
        self.rel, self.parts, self.ext = rel, parts, ext
        self.use_client = self.use_server = self.baas_call = self.browser_client = False
        self.node_server = self.py_server = False
        self.baas = set()
        self.routes = []
        self.links = []
        self.value_score = 0  # 2: one line reads the request and names a value; 1: both, on different lines


# "The browser chooses it" read order (0.6.0): server files that take a value from the request come first.
VALUE_NAME_RE = re.compile(r"\b(?:amount|points?|price|total|credits?|quantity|qty|night|date|limit|role|plan|tier|"
                           r"balance|score|reward|coins?)\b", re.I)
REQUEST_READ_RE = re.compile(r"formData\.get\(|\breq(?:uest)?\.(?:body|json\(|query|params|form|args|get_json)|"
                             r"searchParams|await\s+\w+\.json\(\)|\bbody\.\w")
ACTION_PARAMS_RE = re.compile(r"\bexport\s+(?:async\s+)?function\s+\w+\s*\(")
MAX_VALUE_HANDLERS = 10


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
        seen_value = seen_read = False
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
            names_value = VALUE_NAME_RE.search(line) is not None
            reads = REQUEST_READ_RE.search(line) is not None or (ff.use_server and ACTION_PARAMS_RE.search(line))
            seen_value |= names_value
            seen_read |= bool(reads)
            if names_value and reads:
                ff.value_score = 2
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
        if ff.value_score < 2 and seen_value and seen_read:
            ff.value_score = 1
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
    return add_value_handlers(result, value_handler_order(result, state))


def value_handler_order(result, state):
    """The listed server files, those that read the request and name a value first, then the listed order."""
    score = {ff.rel: ff.value_score for ff in state.files}
    listed = []
    for s in result["shape"]:
        if s["signal"] in ("own-api-routes", "server-actions") and s["path"] not in listed:
            listed.append(s["path"])
    return sorted(listed, key=lambda p: -score.get(p, 0))[:MAX_VALUE_HANDLERS]  # stable: ties keep listed order


def add_value_handlers(result, paths):
    """Add value_handlers only in the room the legacy output leaves: nothing main prints changes. With no room
    for even one path the key is left out (the skill then reads in the listed order)."""
    for n in range(len(paths), -1, -1):
        if n == 0 and paths:
            return result
        out = dict(result)
        out["value_handlers"] = list(paths[:n])
        if len(dumps(out).encode("utf-8")) <= MAX_OUTPUT_BYTES:
            return out
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


# ------------------------------------------------------------------ section: warnings
#
# `--section warnings` runs its own walk and prints one line: each job an app does with two or more libraries
# (several-ways), for example two libraries that send requests to other services, and the runtime packages a
# JavaScript app lists but nothing uses (unused-parts). A library counts only when the app's manifest declares it and
# at least one of the app's own source files imports it; tests, stories, fixtures, examples, comments and .mdx pages
# never count. Nothing from inside a file reaches the output: only safe paths, line numbers, library names from
# JOB_FAMILIES, the words below, and package names from package.json that pass NPM_NAME_RE and MAX_NPM_NAME_CHARS.
#
# 0.8.0 adds a second kind, unused-parts (S-070 K3): runtime packages a JavaScript app lists in package.json that
# nothing in the app uses. It runs only when a readable lockfile covers the app, since the lockfile shows what each
# used package needs. "Code that never runs" was cut by its sample and Python apps are not checked for unused parts
# (S-059, 2026-10-25); see TODOS.md.

WARN_KINDS = ("several-ways", "unused-parts")
WARN_JOBS = ("http", "state", "dates", "forms")
WARN_COVERAGE = ("checked", "below_floor")
WARN_K3_STATES = ("checked", "below_floor", "no_lockfile", "old_lockfile", "files_unread", "manifest_unreadable",
                  "time_limit")
WARN_REASONS = ("max_apps_hit", "manifest_unreadable")
MAX_K1_FINDINGS = 4
MAX_WARNINGS = 6
MAX_WARN_PLACES = 3
WARN_FLOOR_K3_PACKAGES = 5
MAX_CONFIG_TEXT = 262144
MAX_LOCKFILE_BYTES = 33554432  # lockfiles are read as data only: which package needs which
LOCKFILES_READ = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
MAX_NPM_NAME_CHARS = 214
MAX_K3_TEXT_BYTES = 48 * 1024 * 1024  # all K3-only reads (tests, pages, styles, configs) together
MAX_K3_LOCK_BYTES = 96 * 1024 * 1024  # all lockfiles together
MAX_K3_REACH_FILES = 20000  # files reached by following imports out of one app folder
# Folders the walk skips everywhere. Below an app's own top level they can hold code (app/vendor/page.tsx), so an
# app with one, or with an import into one, is not checked for unused parts.
K3_BLIND_DIRS = {"vendor", "build", "out", "dist", "coverage"}
K3_TEXT_EXTS = {".mdx", ".ipynb", ".html", ".htm", ".css", ".scss", ".sass", ".less", ".pcss"}

# A package counts as used when one of its pairs is used (C37). Frozen with the round-4 prototype (S-070).
PAIRED_WITH = {
    "react-dom": ("react", "next", "@remix-run/react", "react-router", "gatsby"),
    "prisma": ("@prisma/client",),
    "@prisma/client": ("prisma",),
    "pg": ("drizzle-orm", "knex", "typeorm", "sequelize", "kysely", "@prisma/adapter-pg", "pg-promise", "@mikro-orm/core"),
    "mysql2": ("drizzle-orm", "knex", "typeorm", "sequelize", "kysely"),
    "sqlite3": ("knex", "typeorm", "sequelize"),
    "better-sqlite3": ("drizzle-orm", "knex", "kysely"),
    "sharp": ("next",),
    "postcss": ("tailwindcss", "autoprefixer"),
    "autoprefixer": ("tailwindcss", "postcss"),
    "typescript": ("next", "vite", "ts-node", "tsx"),
    "@supabase/supabase-js": ("@supabase/ssr", "@supabase/auth-helpers-nextjs", "@supabase/auth-helpers-react"),
    "date-fns": ("react-day-picker",),
    "@emotion/styled": ("@mui/material", "@mui/joy"),
    "@tiptap/pm": ("@tiptap/react", "@tiptap/starter-kit", "novel"),
    "@angular/compiler": ("@angular/platform-browser-dynamic",),
    "@fortawesome/fontawesome-svg-core": ("@fortawesome/react-fontawesome",),
    "quill": ("primevue", "react-quill", "ngx-quill"),
    "@discordjs/opus": ("discord.js",),
    "opusscript": ("discord.js",),
    "parcel-bundler": ("parcel",),
    "@emotion/react": ("@mui/material", "@mui/joy", "@emotion/styled"),
    # database drivers and helpers an ORM loads by itself (never imported by the app)
    "pg-hstore": ("sequelize",),
    "mariadb": ("sequelize", "typeorm"),
    "tedious": ("sequelize", "knex", "typeorm"),
    "mssql": ("knex", "typeorm"),
    "oracledb": ("sequelize", "knex", "typeorm"),
    "mysql": ("knex", "typeorm"),
    "pg-query-stream": ("knex",),
    "pg-native": ("pg",),
    "sql.js": ("typeorm",),
}
PAIRED_PREFIX = {"dumi-theme-": ("dumi",)}  # dumi loads dumi-theme-* by itself
# `node_modules/<pkg>` (also regex-escaped, node_modules\/<pkg>) in a config, CSS, HTML, Gradle file or Podfile: a
# Tailwind content glob, a CSS font url or a native project path means the build reads that package.
NM_REF_RE = re.compile(r"node_modules\\?/((?:@[a-z0-9~][a-z0-9._~-]*\\?/)?[a-z0-9~][a-z0-9._~-]*)")
NATIVE_BUILD_FILES = (".gradle", ".gradle.kts")
NATIVE_BUILD_NAMES = ("podfile",)
CONFIG_NAMES = {"angular.json", "registry.json", "project.json", "nest-cli.json", "makefile", "tox.ini", "setup.cfg",
                ".pre-commit-config.yaml", "pytest.ini", ".flake8", "justfile", "noxfile.py", ".python-version",
                "components.json", "vercel.json", "netlify.toml", "manifest.json", "app.json", "nodemon.json",
                "turbo.json", "deno.json", "firebase.json", "wrangler.toml", "wrangler.json", "fly.toml", "render.yaml",
                "procfile", "dockerfile", "docker-compose.yml", "docker-compose.yaml", "railway.json",
                "vite.config.json"}
CONFIG_DOT_PREFIXES = (".babelrc", ".eslintrc", ".prettierrc", "postcss.config", ".stylelintrc", ".lintstagedrc",
                       ".commitlintrc")
LINT_PREFIXES = ("eslint-config-", "eslint-plugin-", "prettier-plugin-", "babel-plugin-", "babel-preset-")
LITERAL_RE = re.compile(r"""['"`]([A-Za-z0-9_@./~$+\-\[\]()]{2,200})['"`]""")
CSS_IMPORT_RE = re.compile(r"""@(?:import|plugin|use|forward|config|reference)\s+(?:url\()?\s*['"]([^'"]+)['"]""")
TAILWIND_DIRECTIVE_RE = re.compile(r"@tailwind\s+\w+|@apply\s")
PY_MODULE_LITERAL_RE = re.compile(r"""^([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)(?::[A-Za-z_]\w*)?$""")
NPM_NAME_RE = re.compile(r"^(@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]*$")
TOOL_SETTINGS_RE = re.compile(r"^\.([a-z0-9][a-z0-9-]*?)(?:rc(?:\.\w+)?|ignore)$|^([a-z0-9][a-z0-9-]*)\.config\.\w+$")


def _pkg_of(spec):
    """The package an import names (`@scope/name` or `name`), or None for a relative or absolute path."""
    if spec.startswith(("./", "../", "/")) or spec in (".", ".."):
        return None
    segs = spec.split("/")
    if spec.startswith("@"):
        return "/".join(segs[:2]) if len(segs) > 1 else None
    return segs[0]


def _jsonc(text):
    """JSON with // and /* */ comments and trailing commas removed (strings kept), as tsconfig allows. None when it
    cannot be read."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    try:
        obj = json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))
    except (ValueError, RecursionError):
        return None
    return obj if isinstance(obj, dict) else None


def _lock_graph(name, text):
    """{package: packages it depends on or names as a peer} from one lockfile. Read as data only: nothing from a
    lockfile is ever printed."""
    g = {}
    if name == "package-lock.json":
        try:
            obj = json.loads(text)
        except (ValueError, RecursionError):
            return g
        if not isinstance(obj, dict):
            return g
        packages = obj.get("packages")
        for key, ent in (packages.items() if isinstance(packages, dict) else ()):
            if not isinstance(ent, dict) or "node_modules/" not in key:
                continue
            pkg = key.rsplit("node_modules/", 1)[1]
            for f in ("dependencies", "peerDependencies", "optionalDependencies"):
                if isinstance(ent.get(f), dict):
                    g.setdefault(pkg, set()).update(ent[f])
        if not packages:  # lockfile v1: a nested dependencies tree with "requires"
            stack = [obj.get("dependencies")]
            while stack:
                deps = stack.pop()
                for pkg, ent in (deps.items() if isinstance(deps, dict) else ()):
                    if isinstance(ent, dict):
                        req = ent.get("requires")
                        g.setdefault(pkg, set()).update(req if isinstance(req, dict) else ())
                        stack.append(ent.get("dependencies"))
        return g
    cur = sub = None
    in_packages = False
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = len(line) - len(line.lstrip(" "))
        st = line.strip()
        if name == "pnpm-lock.yaml":
            if ind == 0:
                cur = sub = None
                in_packages = st.rstrip(":") in ("packages", "snapshots")
                continue
            if not in_packages:
                continue
            if ind == 2:
                key = st.rstrip(":").strip("'\"").lstrip("/")
                m = re.match(r"^(@[^@/]+/[^@/(]+|[^@/(]+)[@/]", key)
                cur = m.group(1) if m else None
                sub = None
            elif ind == 4:
                sub = st.rstrip(":") if st.endswith(":") and st.rstrip(":") in (
                    "dependencies", "peerDependencies", "optionalDependencies") else None
            elif ind == 6 and cur and sub:
                m = re.match(r"""^['"]?(@?[^:'"\s]+)['"]?\s*:""", st)
                if m:
                    g.setdefault(cur, set()).add(m.group(1))
        else:  # yarn.lock (v1 and berry)
            if ind == 0:
                first = st.rstrip(":").split(",")[0].strip().strip('"')
                at = first.rfind("@")
                cur = first[:at] if at > 0 else None
                sub = None
            elif ind == 2:
                sub = st.rstrip(":") if st.rstrip(":") in ("dependencies", "peerDependencies",
                                                           "optionalDependencies") else None
            elif ind == 4 and cur and sub:
                m = re.match(r"""^"?(@?[^\s":]+)"?[:\s]""", st)
                if m:
                    g.setdefault(cur, set()).add(m.group(1))
    return g


def _lock_info(name, text):
    """A lockfile read as data: {graph, old, importers}, or None when it does not parse as that kind of lockfile.
    old: it records no peer dependencies (yarn v1, npm lockfileVersion 1), so a part a used package needs only as a
    peer would look unused. importers: the folders (relative to the lockfile) it covers as workspaces."""
    if "\n<<<<<<< " in "\n" + text or "\n>>>>>>> " in "\n" + text:
        return None  # merge-conflict markers: half of it is missing
    importers = {""}
    if name == "package-lock.json":
        try:
            obj = json.loads(text)
        except (ValueError, RecursionError):
            return None
        if not isinstance(obj, dict):
            return None
        packages, deps = obj.get("packages"), obj.get("dependencies")
        if isinstance(packages, dict) and packages:
            old = False
            importers |= {k.strip("/") for k in packages if isinstance(k, str) and "node_modules/" not in k
                          and not k.startswith("node_modules")}
        elif isinstance(deps, dict):
            old = True
        else:
            return None
    elif name == "pnpm-lock.yaml":
        first = next((l for l in text.split("\n") if l.strip() and not l.lstrip().startswith("#")), "")
        if not first.startswith("lockfileVersion:"):
            return None
        old = False
        in_importers = False
        for line in text.split("\n"):
            if line and not line.startswith(" "):
                in_importers = line.rstrip().rstrip(":") == "importers"
                continue
            if in_importers and line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
                importers.add(line.strip().rstrip(":").strip("'\"").lstrip("./").rstrip("/") if line.strip() != ".:"
                              else "")
    else:  # yarn.lock
        if "__metadata:" in text:
            old = False
            for m in re.finditer(r"@workspace:([^\",\n]*)", text):
                importers.add(m.group(1).strip().lstrip("./").rstrip("/").rstrip(":"))
        elif "# yarn lockfile v1" in text:
            old = True
        else:
            return None
    importers.discard(".")
    return {"graph": _lock_graph(name, text), "old": old, "importers": importers}


def _dep_lines(text):
    """{name: line} for the runtime dependencies block of a package.json, read as text so each place has a line."""
    lines, block = {}, None
    for i, line in enumerate(text.split("\n"), 1):
        m = re.match(r'^\s*"(dependencies|devDependencies|peerDependencies|optionalDependencies)"\s*:\s*\{', line)
        if m:
            block = None if "}" in line[m.end():] else m.group(1)
            continue
        if block and re.match(r"^\s*\}", line):
            block = None
            continue
        if block == "dependencies":
            m = re.match(r'^\s*"([^"]+)"\s*:', line)
            if m:
                lines.setdefault(m.group(1), i)
    return lines

# One closed table: job id -> libraries that do that job (Y1). Only families a sample stratum covered ship (C8).
JOB_FAMILIES = {
    "http": ("axios", "ky", "got", "node-fetch", "superagent", "requests", "httpx", "aiohttp"),
    "state": ("redux", "@reduxjs/toolkit", "zustand", "jotai", "recoil", "mobx", "valtio"),
    "dates": ("moment", "dayjs", "date-fns", "luxon"),
    "forms": ("react-hook-form", "formik"),
}
PY_LIBS = {"requests", "httpx", "aiohttp"}
# One library under two names: Redux Toolkit is redux (§2.2 lists them as one). A redux import counts as the
# toolkit when the app declares both.
SAME_LIBRARY = {"redux": "@reduxjs/toolkit"}
# aiohttp names that serve requests, not send them: an import of only these is not an HTTP-request library use.
AIOHTTP_SERVER_NAMES = {"web", "web_request", "web_response", "web_exceptions", "web_runner", "web_urldispatcher"}
REQ_LINE_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
EXPORT_FROM_RE = re.compile(r"""\bexport\s+(?:\*|\{[^}]*\})\s*from\s*['"]([^'"\s]+)['"]""")


def _py_norm(name):
    return re.sub(r"[-_.]+", "_", name).lower()


def _toml_deps(text):
    """Names in [project].dependencies and [tool.poetry.dependencies] of a pyproject.toml (python 3.9 has no
    tomllib). None when the file has a shape this small reader does not handle."""
    out, table, in_list = [], None, False
    for raw in text.split("\n"):
        # a "#" after a quote may sit inside a quoted string, so such a line keeps its comment (prototype rule)
        s = (raw.split("#")[0] if '"' not in raw.split("#")[0] else raw).strip()
        if not s:
            continue
        m = re.match(r"^\[([^\]]+)\]$", s)
        if m and not in_list:
            table = m.group(1).strip()
            continue
        if table == "project":
            if in_list:
                out += re.findall(r"""['"]\s*([A-Za-z0-9][A-Za-z0-9._-]*)""", s)
                in_list = "]" not in s
                continue
            m = re.match(r"^dependencies\s*=\s*\[(.*)$", s)
            if m:
                out += re.findall(r"""['"]\s*([A-Za-z0-9][A-Za-z0-9._-]*)""", m.group(1))
                in_list = "]" not in m.group(1)
        elif table == "tool.poetry.dependencies":
            m = re.match(r"""^['"]?([A-Za-z0-9][A-Za-z0-9._-]*)['"]?\s*=""", s)
            if not m:
                return None
            if m.group(1).lower() != "python":
                out.append(m.group(1))
    return None if in_list else out


def _req_names(text):
    """Names in a requirements.txt. Options (-e, --index-url) and bare URL lines name nothing; reading stops at
    -r, which this reader does not follow."""
    out = []
    for raw in text.split("\n"):
        line = raw.split(" #")[0].split("\t#")[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement")):
            break
        if line.startswith("-"):
            continue
        if "://" in line and "@" not in line.split("://")[0]:
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*\S+://", line)
            if m:
                out.append(m.group(1))
            continue
        m = REQ_LINE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


class WarnState(ArchState):
    """An architecture walk (for package.json manifests) that also records Python manifests and the libraries
    each code file imports. Test files never reach on_lines (walk skips them)."""

    def __init__(self, opts):
        ArchState.__init__(self, opts)
        self.census_lines = False  # the warnings read only imports: no census rules, stop-line or sample-key work
        self.uncapped = False  # --uncapped (sample runs only): every unused-parts place and every finding
        self.imports = {}  # rel -> [(library spec or ("py", module), line)]
        self.read = set()  # code files whose lines were read
        self.py_manifests = {}  # dir tuple -> set of normalised names, or None when one could not be read
        self.pkg_text = set()  # dir tuples holding a package.json, parsed or not
        self.venv_dirs = set()  # folders holding pyvenv.cfg: a vendored Python environment, not app code
        # unused-parts (K3) records, kept apart from the several-ways ones above so that kind never changes
        self.known = set()  # every file the walk saw (not ignored)
        self.dirs = set()
        self.k3_imports = {}  # rel -> [(spec or ("py", dots, module, names), line)], tests and .mdx pages included
        self.k3_read = set()  # files whose lines K3 read
        self.literals = set()  # string literals in read files, configs and HTML
        self.py_literals = set()  # first dotted segments of Python string literals
        self.css_specs = []  # (css rel, spec)
        self.tailwind_dirs = set()
        self.config_texts = {}  # rel -> text of a config, HTML page or tsconfig, read for package names
        self.config_code = set()  # configs written as code (vite.config.ts): their text is kept from on_lines
        self.tsconfigs = {}  # dir tuple -> parsed tsconfig.json / jsconfig.json, or None when unreadable
        self.tsconfig_files = {}  # rel -> parsed tsconfig*.json, for "extends"
        self.pkg_lines = {}  # dir tuple -> {name: line} of package.json runtime dependencies
        self.locks = {}  # dir tuple -> [lockfile info]: graph, old (records no peers), importers (folders it covers)
        self.blind = []  # rel paths of linked code files and folders (never read)
        self.blind_dirs = []  # skipped folders named in K3_BLIND_DIRS
        self.k3_bytes = 0
        self.k3_lock_bytes = 0
        self.k3_over = False  # a K3 read budget ran out: K3 stays quiet everywhere
        self.nm_refs = []  # (rel, package) from node_modules/<pkg> paths in native build files and CSS
        self.unread = set()  # code files the walk saw but could not read
        self._pending = None
        self._unread_seen = 0
        self.stats["names_withheld"] = 0

    def ignored(self, parts):
        """Editor backups, vendored Python environments and Vite's temp config copies (RULINGS L5)."""
        if ".history" in parts or "site-packages" in parts or ".timestamp-" in parts[-1]:
            return True
        return any(tuple(parts[:k]) in self.venv_dirs for k in range(1, len(parts)))

    def _read_text(self, path, cap=None):
        try:
            data, _ = read_file(path, self, cap=MAX_META_BYTES if cap is None else cap)
        except OSError:
            return None
        if data is None or b"\x00" in data[:BINARY_SNIFF_BYTES]:
            return None
        return data.decode("utf-8", errors="replace")

    def _unread_count(self):
        s = self.stats
        return s["files_skipped_oversize"] + s["files_skipped_special"] + s["files_errored"]

    def _settle(self):
        """The code file announced last was not read when the walk's unread counters moved since: K3 skips its app."""
        if self._pending is not None:
            if self._pending not in self.k3_read and self._unread_count() > self._unread_seen:
                self.unread.add(self._pending)
            self._pending = None
        self._unread_seen = self._unread_count()

    def on_dir(self, parts):
        self._settle()
        ArchState.on_dir(self, parts)
        self.dirs.add("/".join(parts))

    def on_meta(self, path, parts, lower, is_link):
        self._settle()
        if lower == "pyvenv.cfg":
            self.venv_dirs.add(tuple(parts[:-1]))
        if self.ignored(parts):
            return True  # not read, not counted, not a manifest
        self._k3_meta(path, parts, lower, is_link)
        d = tuple(parts[:-1])
        if not is_link and not _not_app(d):
            if lower in ("requirements.txt", "pyproject.toml"):
                text = self._read_text(path)
                names = None if text is None else _req_names(text) if lower == "requirements.txt" \
                    else _toml_deps(text)
                if names is None or self.py_manifests.get(d, set()) is None:
                    self.py_manifests[d] = None  # unreadable: this folder declares no Python library
                else:
                    self.py_manifests.setdefault(d, set()).update(_py_norm(n) for n in names)
            elif lower == "package.json" and self._read_text(path) is not None:
                self.pkg_text.add(d)
            elif lower.endswith(".ipynb"):
                self._notebook(path, parts)
                return True
        return ArchState.on_meta(self, path, parts, lower, is_link)

    def _notebook_code(self, path, cap=None):
        """The code cells of a Python notebook as lines, or None."""
        text = self._read_text(path, cap)
        try:
            nb = json.loads(text) if text is not None else None
        except (ValueError, RecursionError):
            nb = None  # a notebook that will not parse is skipped; it never stops the section
        if not isinstance(nb, dict):
            return None
        meta = nb.get("metadata")
        kernel = meta.get("kernelspec") if isinstance(meta, dict) else None
        if (kernel.get("language", "python") if isinstance(kernel, dict) else "python") != "python":
            return None
        code = []
        cells = nb.get("cells")
        for cell in cells if isinstance(cells, list) else ():
            if isinstance(cell, dict) and cell.get("cell_type") == "code":
                src = cell.get("source")
                src = "".join(s for s in src if isinstance(s, str)) if isinstance(src, list) else \
                    (src if isinstance(src, str) else "")
                code += src.split("\n")
        return code

    def _notebook(self, path, parts):
        code = self._notebook_code(path)
        if code is not None:
            self._capture(parts, ".py", code)

    def on_lines(self, parts, ext, lines):
        self._settle()
        if not self.ignored(parts):  # the architecture line analysis is not needed here: manifests come from on_meta
            self._capture(parts, ext, lines)
            self._k3_capture(parts, ext, lines)
            rel = "/".join(parts)
            if rel in self.config_code:
                self.config_texts[rel] = "\n".join(lines)[:MAX_CONFIG_TEXT]

    # ---- unused-parts (K3): side effects only. Nothing here changes what on_meta returns, so the walk, the
    # several-ways records and every count stay as they were.

    def _k3_meta(self, path, parts, lower, is_link):
        rel = "/".join(parts)
        self.known.add(rel)
        d = tuple(parts[:-1])
        ext = os.path.splitext(lower)[1]
        if lower in LOCKFILES_READ:
            if not is_link:
                text = self._k3_text(path, MAX_LOCKFILE_BYTES, lock=True)
                info = _lock_info(lower, text) if text is not None else None
                if info is not None:  # only a lockfile that parses covers anything
                    self.locks.setdefault(d, []).append(info)
            return
        if lower in SKIP_BASENAMES:
            return
        if not is_link and (lower.endswith(NATIVE_BUILD_FILES) or lower in NATIVE_BUILD_NAMES):
            text = self._k3_text(path, MAX_CONFIG_TEXT)
            if text is not None:
                self._nm(rel, text)
        if is_link:
            if ext in SCAN_EXTS or ext in K3_TEXT_EXTS or os.path.isdir(path):
                self.blind.append(rel)  # a linked file or folder is never read: its imports are unseen
            return
        is_test = TEST_FILE_RE.search(parts[-1]) is not None or any(p.lower() in TEST_DIRS for p in parts)
        if ext in SCAN_EXTS and is_test and (ext in JS_EXTS or ext == ".py"):
            text = self._k3_text(path, self.opts.max_file_bytes)  # the census skips tests; K3 counts their imports
            if text is not None:
                self._k3_capture(parts, ext, text.split("\n"))
            return
        if ext == ".ipynb":
            code = self._notebook_code(path, self.opts.max_file_bytes)
            if code is not None:
                self._k3_capture(parts, ".py", code)
            return
        if ext == ".mdx":
            text = self._k3_text(path, self.opts.max_file_bytes)
            if text is not None:
                self._k3_capture(parts, ".jsx", text.split("\n"))
            return
        if ext in (".html", ".htm"):
            text = self._k3_text(path, MAX_CONFIG_TEXT)
            if text is not None:
                self._literals(text)
                self.config_texts[rel] = text
            return
        if ext in (".css", ".scss", ".sass", ".less", ".pcss"):
            text = self._k3_text(path, MAX_CONFIG_TEXT)
            if text is not None:
                self.css_specs += [(rel, spec) for spec in CSS_IMPORT_RE.findall(text)]
                self._nm(rel, text)
                if TAILWIND_DIRECTIVE_RE.search(text):
                    self.tailwind_dirs.add(d)
            return
        if lower in ("tsconfig.json", "jsconfig.json") or (lower.startswith("tsconfig") and ext == ".json"):
            text = self._k3_text(path, MAX_CONFIG_TEXT)
            obj = _jsonc(text) if text is not None else None
            if lower in ("tsconfig.json", "jsconfig.json") and self.tsconfigs.get(d) is None:
                self.tsconfigs[d] = obj
            self.tsconfig_files[rel] = obj
            if text is not None:
                self.config_texts[rel] = text
            return
        if lower in ("requirements.txt", "pyproject.toml"):
            return  # Python apps are not checked for unused parts
        if lower == "package.json":
            text = self._k3_text(path)
            if text is not None:
                self.pkg_lines[d] = _dep_lines(text)
        is_config = (".config." in lower or lower.startswith(CONFIG_DOT_PREFIXES) or lower in CONFIG_NAMES
                     or (len(parts) > 1 and parts[-2] == ".storybook")
                     or (len(parts) > 2 and parts[-3] == ".github" and parts[-2] == "workflows"))
        if is_config and ext not in SCAN_EXTS:
            text = self._k3_text(path, MAX_CONFIG_TEXT)
            if text is not None:
                self.config_texts[rel] = text
                self._literals(text)
        elif is_config:
            self.config_code.add(rel)
        if ext in SCAN_EXTS and not lower.endswith(SKIP_EXT_SUFFIXES):
            self._pending = rel

    def on_excluded(self, parts):
        if parts[-1] in K3_BLIND_DIRS and not self.ignored(parts):
            self.blind_dirs.append(tuple(parts))

    def _k3_text(self, path, cap=None, lock=False):
        """A K3-only read, inside its own byte budget. Once a budget runs out K3 reads nothing more and stays quiet."""
        if self.k3_over:
            return None
        text = self._read_text(path, cap)
        if text is not None:
            if lock:
                self.k3_lock_bytes += len(text)
            else:
                self.k3_bytes += len(text)
            if self.k3_lock_bytes > MAX_K3_LOCK_BYTES or self.k3_bytes > MAX_K3_TEXT_BYTES:
                self.k3_over = True
                return None
        return text

    def _nm(self, rel, text):
        for p in set(NM_REF_RE.findall(text)):
            self.nm_refs.append((rel, p.replace("\\", "")))

    def _literals(self, text):
        for lit in LITERAL_RE.findall(text):
            lit = lit.strip("/")
            if lit:
                self.literals.add(lit.lstrip("./"))
                self.literals.add(os.path.splitext(lit.rsplit("/", 1)[-1])[0])

    def _k3_capture(self, parts, ext, lines):
        """Every import of a JavaScript or Python file, and the string literals of any read file."""
        rel = "/".join(parts)
        self.k3_read.add(rel)
        imps = []
        is_js = ext in JS_EXTS
        for i, line in enumerate(lines, 1):
            if (i % DEADLINE_LINE_TICK == 0 or len(line) > 512) and self.over_deadline():
                break
            if len(line) > LINE_CLIP_CHARS:
                line = line[:LINE_CLIP_CHARS]
            stripped = line.lstrip()
            if stripped.startswith(("//", "/*", "* ", "#")) or stripped == "*":
                continue  # a commented-out import is not a use
            if is_js:
                imps += [(spec, i) for spec in JS_IMPORT_RE.findall(line)]
                m = EXPORT_FROM_RE.search(line)
                if m and (m.group(1), i) not in imps:
                    imps.append((m.group(1), i))
            elif ext == ".py":
                m = PY_FROM_RE.match(line)
                if m:
                    imps.append((("py", len(m.group(1)), m.group(2) or "", PY_NAME_RE.findall(m.group(3) or "")), i))
                else:
                    m = PY_IMPORT_RE.match(line)
                    if m:
                        for mod in m.group(1).split(","):
                            mod = mod.strip().split(" as ")[0].strip()
                            if mod:
                                imps.append((("py", 0, mod, []), i))
                for lit in LITERAL_RE.findall(line):
                    mm = PY_MODULE_LITERAL_RE.match(lit)
                    if mm:
                        self.py_literals.add(mm.group(1).split(".")[0])
                        self.literals.add(mm.group(1).replace(".", "/"))
            for lit in LITERAL_RE.findall(line):
                lit = lit.strip("/")
                if lit:
                    self.literals.add(lit.lstrip("./"))
                    self.literals.add(os.path.splitext(lit.rsplit("/", 1)[-1])[0])
        if imps:
            self.k3_imports[rel] = imps

    def _capture(self, parts, ext, lines):
        rel = "/".join(parts)
        self.read.add(rel)
        is_js = ext in JS_EXTS
        if not is_js and ext != ".py":
            return
        imps = []
        for i, line in enumerate(lines, 1):
            if (i % DEADLINE_LINE_TICK == 0 or len(line) > 512) and self.over_deadline():
                break
            if len(line) > LINE_CLIP_CHARS:
                line = line[:LINE_CLIP_CHARS]
            stripped = line.lstrip()
            if stripped.startswith(("//", "/*", "* ", "#")) or stripped == "*":
                continue  # a commented-out import is not a use
            if is_js:
                specs = JS_IMPORT_RE.findall(line)
                m = EXPORT_FROM_RE.search(line)
                if m and m.group(1) not in specs:
                    specs.append(m.group(1))
                imps += [(s, i) for s in specs]
            else:
                m = PY_FROM_RE.match(line)
                if m:
                    if not m.group(1) and m.group(2):
                        names = set(PY_NAME_RE.findall(m.group(3) or ""))
                        serves = m.group(2) == "aiohttp" and bool(names) and names <= AIOHTTP_SERVER_NAMES
                        imps.append((("py", m.group(2).split(".")[0], serves or m.group(2).startswith("aiohttp.web")),
                                     i))
                    continue
                m = PY_IMPORT_RE.match(line)
                if m:
                    for mod in m.group(1).split(","):
                        mod = mod.strip().split(" as ")[0].strip()
                        if mod:
                            imps.append((("py", mod.split(".")[0], mod.startswith("aiohttp.web")), i))
        if imps:
            self.imports[rel] = imps


class _K3Resolver(_Resolver):
    """The payment resolver, plus what unused-parts needs: tsconfig path aliases, workspace packages followed to
    their entry file, and a stem with several matching files left unplaced (never the first one picked)."""

    def __init__(self, state):
        _Resolver.__init__(self, state)
        self.pkg_dirs = {}
        for d, man in state.manifests.items():
            name = man.get("name")
            if isinstance(name, str) and d:
                self.pkg_dirs[name] = d
        self.alias_cache = {}

    def files_exist(self, cands):
        seen, out = set(), []
        for c in cands:
            if c in self.state.known and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _tsconfig_for(self, parts):
        for k in range(len(parts) - 1, -1, -1):
            d = tuple(parts[:k])
            if d in self.state.tsconfigs:
                return d, self._load_ts(d)
        return None, None

    def _load_ts(self, d):
        if d in self.alias_cache:
            return self.alias_cache[d]
        obj = self.state.tsconfigs.get(d)
        result = None
        if obj is not None:
            co = obj.get("compilerOptions") if isinstance(obj.get("compilerOptions"), dict) else {}
            result = {"paths": {}, "baseUrl": None}
            ext = obj.get("extends")
            if isinstance(ext, str) and ext.startswith("."):
                target = _norm(list(d) + ext.split("/"))
                if target is None:
                    result = None
                else:
                    tpath = "/".join(target)
                    if not tpath.endswith(".json"):
                        tpath += ".json"
                    pobj = self.state.tsconfig_files.get(tpath)
                    if pobj is not None:  # one level of extends, as the sample ran it
                        pd = tuple(tpath.split("/")[:-1])
                        pco = pobj.get("compilerOptions") if isinstance(pobj.get("compilerOptions"), dict) else {}
                        if isinstance(pco.get("paths"), dict):
                            result["paths"] = {k: (v, pd) for k, v in pco["paths"].items()}
                        if isinstance(pco.get("baseUrl"), str):
                            result["baseUrl"] = (pco["baseUrl"], pd)
            if result is not None:
                if isinstance(co.get("paths"), dict):
                    result["paths"] = {k: (v, d) for k, v in co["paths"].items()}
                if isinstance(co.get("baseUrl"), str):
                    result["baseUrl"] = (co["baseUrl"], d)
        self.alias_cache[d] = result
        return result

    def targets(self, parts, imp):
        """The files this import reaches, or [] when it reaches outside code or cannot be placed."""
        if isinstance(imp, tuple):
            got = self._py(parts, imp[1], imp[2], imp[3])
            return self.files_exist(got) if got else []
        clean = imp.split("?")[0]
        if not clean or imp.startswith(EXTERNAL_PREFIXES):
            return []
        ext = os.path.splitext(clean)[1].lower()
        if ext and ext not in RESOLVE_EXTS and ext not in (".js", ".jsx", ".mjs", ".cjs"):
            if ext.lstrip(".").isalnum() and len(ext) <= 6:
                return []
        if clean.startswith(("./", "../")) or clean in (".", ".."):
            segs = _norm(list(parts[:-1]) + clean.split("/"))
            return self._pick([] if segs is None else _js_candidates(segs))
        if clean.startswith("/"):
            return []
        segs = clean.split("/")
        pkg = _pkg_of(clean)
        if segs[0] in NODE_BUILTINS:
            return []
        tsd, ts = self._tsconfig_for(parts)
        if ts is not None:
            for pat, (targets, base_dir) in sorted(ts["paths"].items(), key=lambda kv: -len(kv[0])):
                if not isinstance(targets, list):
                    continue
                if pat.endswith("*"):
                    if not clean.startswith(pat[:-1]):
                        continue
                    rest = clean[len(pat) - 1:]
                elif clean == pat:
                    rest = ""
                else:
                    continue
                bdir = list(base_dir)
                if ts["baseUrl"]:
                    bu, bud = ts["baseUrl"]
                    bdir = _norm(list(bud) + bu.split("/")) or list(bud)
                cands = []
                for t in targets:
                    if isinstance(t, str):
                        segs2 = _norm(bdir + (t.replace("*", rest) if "*" in t else t).split("/"))
                        if segs2:
                            cands += _js_candidates(segs2)
                return self._pick(cands)
        elif tsd is not None and self.state.tsconfigs.get(tsd) is None and clean.startswith(("@/", "~/", "#")):
            return []  # an unreadable tsconfig: its aliases are unknown
        if pkg in self.pkg_dirs:
            return self._workspace(pkg, clean)
        if pkg in self.local_pkgs or pkg in self.deps:
            return []
        if ts is not None and ts["baseUrl"]:
            bu, bud = ts["baseUrl"]
            segs2 = _norm(list(bud) + bu.split("/") + clean.split("/"))
            if segs2:
                got = self._pick(_js_candidates(segs2))
                if got:
                    return got
        if clean[0] in "@~#$" and (clean.startswith(("@/", "~/", "#/", "$")) or "/" not in clean):
            cands = []
            for root in self._roots(parts):
                s2 = _norm(root + clean[1:].lstrip("/").split("/"))
                if s2:
                    cands += _js_candidates(s2)
            return self._pick(cands)
        return []  # a package this app does not list: installed by a parent or a tool

    def _pick(self, cands):
        real = sorted(set(self.files_exist(cands)))
        return real if len(real) == 1 else []  # two files for one stem: not placed (E4)

    def _workspace(self, pkg, clean):
        d = list(self.pkg_dirs[pkg])
        man = self.state.manifests.get(tuple(d), {})
        sub = clean[len(pkg):].lstrip("/")
        if sub:
            return self._pick(_js_candidates(d + sub.split("/")) + _js_candidates(d + ["src"] + sub.split("/")))
        entries = [man.get(k) for k in ("source", "module", "main", "types", "typings") if isinstance(man.get(k), str)]
        ex = man.get("exports")
        if isinstance(ex, str):
            entries.append(ex)
        elif isinstance(ex, dict):
            dot = ex.get(".", ex)
            if isinstance(dot, str):
                entries.append(dot)
            elif isinstance(dot, dict):
                entries += [v for v in dot.values() if isinstance(v, str)]
        cands = []
        for e in entries:
            s2 = _norm(d + e.split("/"))
            if s2:
                cands += _js_candidates(s2)
        cands += _js_candidates(d + ["index"]) + _js_candidates(d + ["src", "index"])
        hit = self.files_exist(cands)
        return hit[:1] + [h for h in hit[1:] if h.endswith(("index.ts", "index.tsx", "index.js"))] if hit else []


def _warn_app_roots(state):
    roots = set(d for d in state.manifests if not _not_app(d) and not state.ignored(list(d) + ["x"]))
    roots |= set(d for d in state.py_manifests if not _not_app(d))
    roots |= set(d for d in state.pkg_text if not _not_app(d))  # a package.json that would not parse
    return sorted(roots)


def _warn_owner(parts, roots):
    for k in range(len(parts) - 1, -1, -1):
        if tuple(parts[:k]) in roots:
            return tuple(parts[:k])
    return None


def _k1_source(rel):
    """The app's own source: never tests, stories, fixtures or examples (Python test files included)."""
    parts = rel.split("/")
    low = parts[-1].lower()
    return not (TEST_FILE_RE.search(parts[-1]) or any(p.lower() in NOT_APP_DIRS for p in parts)
                or ".stories." in rel or low.startswith("test_") or low.endswith("_test.py") or low == "conftest.py")


def warn_findings(state):
    """All findings in helper order (kind, then app folder, then job id), and per-app coverage. Several-ways runs
    first for every app, exactly as in 0.7.0; unused-parts then runs as its own pass, within what is left of the
    post-walk budget, so it can never cost a several-ways finding."""
    state._settle()
    state.post_walk_started = time.monotonic()
    walk_reasons = set(state.reasons)
    roots = _warn_app_roots(state)
    if len(roots) > MAX_APPS:
        roots = roots[:MAX_APPS]
        state.reason("max_apps_hit")
    rootset = set(roots)
    files_by_app = {r: [] for r in roots}
    for rel in sorted(state.read):
        if _k1_source(rel):
            o = _warn_owner(rel.split("/"), rootset)
            if o is not None:
                files_by_app[o].append(rel)
    findings, coverage, done = [], [], []
    for app in roots:
        if _late(state):
            break
        if app and safe_rel(list(app)) is None:
            state.stats["paths_withheld"] += 1  # a folder name not safe to print: the app is left out, never printed
            continue
        app_name = "/".join(app) or "."
        declared = _deps(state.manifests.get(app) or {}, ("dependencies", "devDependencies"))
        declared |= state.py_manifests.get(app) or set()
        checked = False
        for job in WARN_JOBS:
            family = [lib for lib in JOB_FAMILIES[job] if lib in declared]
            alias = {k: v for k, v in SAME_LIBRARY.items() if k in family and v in family}
            family = [lib for lib in family if lib not in alias]
            # one finding never pairs a JavaScript library with a Python one: they can never be merged
            for libs in ([x for x in family if x not in PY_LIBS], [x for x in family if x in PY_LIBS]):
                if len(libs) < 2:
                    continue  # the floor (C23): two declared libraries of one family, in one language
                checked = True
                finding = _several_ways(state, files_by_app[app], app_name, job, libs, alias)
                if finding:
                    findings.append(finding)
        cov = {"app": app_name, "k1": "checked" if checked else "below_floor"}
        coverage.append(cov)
        done.append((app, app_name, cov))
    findings.sort(key=lambda f: (f["app"], f["job"], f["places"][0]["name"]))
    unused = []
    try:
        ctx = _k3_context(state, roots, rootset, walk_reasons)
    except _K3OutOfTime:
        ctx = None
    for app, app_name, cov in done:
        if ctx is None:
            cov["k3"] = "time_limit"
            continue
        try:
            cov["k3"], finding = _unused_parts(state, ctx, app, app_name)
        except _K3OutOfTime:
            cov["k3"], finding, ctx = "time_limit", None, None
        if finding:
            unused.append(finding)
    unused.sort(key=lambda f: f["app"])
    return findings, unused, coverage


class _K3OutOfTime(Exception):
    """Unused-parts used up the post-walk budget: it stops and says so, and never sets deadline_hit."""


def _k3_tick(state):
    if time.monotonic() - state.post_walk_started > POST_WALK_BUDGET_S:
        raise _K3OutOfTime()


def _k3_context(state, roots, rootset, walk_reasons):
    """What unused-parts needs across the whole repo: the packages each file imports, the files each file
    reaches (imports are followed out of the app folder), each app's own files, and which apps have code the walk
    could not see."""
    res = _K3Resolver(state)
    used_specs = {r: set() for r in roots}  # package specs per app folder (owner of the importing file)
    file_specs = {}  # rel -> packages (and Python top modules) it imports
    fwd = {}  # rel -> files it imports
    unread = set(state.unread) | set(state.blind)
    for n, rel in enumerate(sorted(state.k3_imports)):
        if n % 64 == 0:
            _k3_tick(state)
        parts = rel.split("/")
        o = _warn_owner(parts, rootset)
        for imp, _line in state.k3_imports[rel]:
            if isinstance(imp, str):
                clean = imp.split("?")[0]
                pkg = _pkg_of(clean)
                if pkg:
                    file_specs.setdefault(rel, set()).add(pkg)
                    if o is not None:
                        used_specs[o].add(pkg)
                elif clean.startswith("."):
                    segs = _norm(list(parts[:-1]) + clean.split("/"))
                    if segs and any(x in K3_BLIND_DIRS for x in segs[:-1]):
                        unread.add(rel)  # an import into a folder the walk skips: code K3 cannot see
            elif imp[1] == 0 and imp[2]:
                file_specs.setdefault(rel, set()).add(imp[2].split(".")[0])
            for t in res.targets(parts, imp):
                if t != rel:
                    fwd.setdefault(rel, set()).add(t)
    for d in state.blind_dirs:
        if tuple(d[:-1]) not in rootset:  # below an app's own top level: a route or code folder, not build output
            unread.add("/".join(d))
    by_root = {r: {"known": [], "imports": [], "configs": [], "css": [], "nm": [], "code": []} for r in roots}

    def put(kind, rel, item):
        o = _warn_owner(rel.split("/"), rootset)
        if o is not None:
            by_root[o][kind].append(item)

    for rel in state.known:
        put("known", rel, rel)
    for rel in state.k3_imports:
        put("imports", rel, rel)
    for rel, text in state.config_texts.items():
        put("configs", rel, text)
    for rel, spec in state.css_specs:
        put("css", rel, spec)
    for rel, pkg in state.nm_refs:
        put("nm", rel, pkg)
    for rel in state.config_code:
        put("code", rel, rel)
    _k3_tick(state)
    whole = bool(walk_reasons & {"max_files_hit", "max_total_bytes_hit", "dirs_unreadable", "dirs_truncated"})
    whole = whole or state.k3_over or (state.stats["files_errored"] > 0 and not state.unread)
    unread_apps = {_warn_owner(u.split("/"), rootset) for u in unread}
    lit_heads = {lit.split("/", 1)[0] for lit in state.literals if len(lit) < 80 and "/" in lit}
    return {"res": res, "roots": roots, "rootset": rootset, "used_specs": used_specs, "file_specs": file_specs,
            "fwd": fwd, "whole_unread": whole, "unread_apps": unread_apps, "by_root": by_root, "lit_heads": lit_heads}


def _under_roots(ctx, folder):
    return [r for r in ctx["roots"] if _under(r, folder)]


def _gather(ctx, folder, kind):
    """Every item of one kind from files under folder (its own and any nested app's)."""
    out = []
    for r in _under_roots(ctx, folder):
        out += ctx["by_root"][r][kind]
    return out


def _covering_locks(state, app):
    """The lockfiles that cover app: its own folder's, and a folder above whose lockfile lists app as a workspace."""
    out = list(state.locks.get(app, ()))
    for k in range(len(app) - 1, -1, -1):
        rel = "/".join(app[k:])
        out += [info for info in state.locks.get(tuple(app[:k]), ()) if rel in info["importers"]]
    return out


def _unused_parts(state, ctx, app, app_name):
    """(coverage state, finding or None) for one app: runtime packages its package.json lists that nothing uses."""
    if ctx["whole_unread"] or app in ctx["unread_apps"]:
        return "files_unread", None
    if app in state.pkg_text and app not in state.manifests:
        state.reason("manifest_unreadable")
        return "manifest_unreadable", None
    man = state.manifests.get(app) or {}
    res = ctx["res"]
    runtime = man.get("dependencies") if isinstance(man.get("dependencies"), dict) else {}
    mrel = ("/".join(app) + "/" if app else "") + "package.json"
    cands = []  # (name, line)
    for name, ver in runtime.items():
        if not isinstance(name, str) or name.startswith("@types/") or name in res.pkg_dirs:
            continue
        if isinstance(ver, str) and ver.startswith(LOCAL_DEP_PREFIXES):
            continue  # the repo's own code (workspace:, file:, link:), never a candidate (C52)
        cands.append((name, state.pkg_lines.get(app, {}).get(name)))
    if len(cands) < WARN_FLOOR_K3_PACKAGES:
        return "below_floor", None
    locks = _covering_locks(state, app)
    if not locks:
        return "no_lockfile", None  # without a lockfile the check cannot see what a used package needs
    if all(info["old"] for info in locks):
        return "old_lockfile", None  # it records no peers: a part needed only as a peer would look unused
    used = _k3_used(state, ctx, app, man)
    if used is None:
        return "time_limit", None
    unused, withheld = [], 0
    for name, line in cands:
        if used(name):
            continue
        if line is None or len(name) > MAX_NPM_NAME_CHARS or not NPM_NAME_RE.match(name):
            withheld += 1  # never printed (C51)
            continue
        unused.append({"path": mrel, "line": line, "name": name})
    state.stats["names_withheld"] += withheld
    if not unused:
        return "checked", None
    if safe_rel(mrel.split("/")) is None:
        state.stats["paths_withheld"] += 1
        return "checked", None
    unused.sort(key=lambda p: (p["path"], p["line"], p["name"]))
    places = unused if state.uncapped else unused[:MAX_WARN_PLACES]
    return "checked", {"kind": "unused-parts", "app": app_name, "count": len(unused), "places": places,
                       "more": len(unused) - len(places)}


def _mentions(text, name):
    """name appears in text as a whole name (not inside a longer one). The substring test is the fast path."""
    return name in text and re.search(r"(?<![\w@/.-])" + re.escape(name) + r"(?![\w-])", text) is not None


def _k3_used(state, ctx, app, man):
    """A test: is this runtime package used by the app? Imports (followed out of the folder), stylesheets, configs,
    scripts, tool settings files, string literals, pairs and lockfile needs, to a fixed point. None when following
    imports reached MAX_K3_REACH_FILES files."""
    rootset, res = ctx["rootset"], ctx["res"]
    below = [r for r in ctx["roots"] if r[:len(app)] == app]
    for dep in _deps(man, ("dependencies", "devDependencies")):
        wd = res.pkg_dirs.get(dep)  # a workspace package this app depends on: what it imports counts here too
        if wd is not None and wd in rootset and wd not in below:
            below.append(wd)
    specs = set()
    for r in below:
        specs |= ctx["used_specs"][r]
    seen = set()
    for r in below:
        seen.update(_gather(ctx, r, "imports"))
    stack, reached = list(seen), 0
    while stack:
        for t in ctx["fwd"].get(stack.pop(), ()):
            if t not in seen:
                seen.add(t)
                stack.append(t)
                reached += 1
                if reached > MAX_K3_REACH_FILES:
                    return None
    _k3_tick(state)
    for f in seen:
        specs |= ctx["file_specs"].get(f, set())
    for spec in _gather(ctx, app, "css"):
        p = _pkg_of(spec.lstrip("~"))
        if p:
            specs.add(p)
    under = _gather(ctx, app, "known")
    exts_seen = {os.path.splitext(k)[1] for k in under}
    for ext, pkg in ((".svelte", "svelte"), (".vue", "vue"), (".astro", "astro")):
        if ext in exts_seen:
            specs.add(pkg)
    if any(d[:len(app)] == app for d in state.tailwind_dirs):
        specs.add("tailwindcss")
    if any(d[:len(app)] == app for d in state.tsconfigs):
        specs.add("typescript")
    if exts_seen & {".scss", ".sass"}:
        specs |= {"sass", "node-sass", "sass-embedded"}
    names_seen = {k.rsplit("/", 1)[-1].lower() for k in under}
    scripts = man.get("scripts") if isinstance(man.get("scripts"), dict) else {}
    if any(n.startswith((".eslintrc", "eslint.config")) for n in names_seen) or "next lint" in json.dumps(scripts):
        specs.add("eslint")
    if any(n.startswith((".prettierrc", "prettier.config")) for n in names_seen):
        specs.add("prettier")
    tool_cfg = set()  # a tool's own settings file in the app (.jshintrc, .jshintignore, x.config.js, supabase/config.toml)
    for n in names_seen:
        m = TOOL_SETTINGS_RE.match(n)
        if m:
            tool_cfg.add(m.group(1) or m.group(2))
    tool_cfg |= {k.split("/")[-2] for k in under if k.endswith("/config.toml")}
    if any(n.startswith("test_") and n.endswith(".py") or n == "conftest.py" or n.endswith("_test.py")
           for n in names_seen):
        specs |= {"pytest", "pytest_cov", "pytest_asyncio", "pytest_mock", "pytest_xdist", "coverage"}
    cfg_text = " ".join(_gather(ctx, app, "configs"))
    specs |= {x.replace("\\", "") for x in NM_REF_RE.findall(cfg_text)}
    specs |= set(_gather(ctx, app, "nm"))
    for r in _gather(ctx, app, "code"):
        for imp, _ in state.k3_imports.get(r, ()):
            if isinstance(imp, str) and _pkg_of(imp):
                specs.add(_pkg_of(imp))
    script_text = " ".join(v for v in scripts.values() if isinstance(v, str))
    other_fields = json.dumps({k: v for k, v in man.items() if k not in (
        "dependencies", "devDependencies", "peerDependencies", "optionalDependencies", "name", "scripts")})
    mention_text = cfg_text + " " + script_text + " " + other_fields
    runtime = man.get("dependencies") if isinstance(man.get("dependencies"), dict) else {}
    py_used = set(state.py_literals)
    for r in below:
        py_used |= ctx["used_specs"][r]
    normed_used = {_py_norm(x) for x in specs | py_used}
    literals, lit_heads = state.literals, ctx["lit_heads"]
    _k3_tick(state)

    def direct(name):
        _k3_tick(state)
        if name in specs or any(x.startswith(name + "/") for x in specs):
            return True
        if _mentions(mention_text, name):
            return True
        if name.startswith(LINT_PREFIXES):
            short = name.split("-", 2)[-1]
            if short in mention_text or short in literals or short in lit_heads:
                return True
        if name in literals or (name.startswith("@") and name.replace("/eslint-plugin", "") in literals):
            return True  # named as a string in the app's code or config
        if name.startswith("@") and name.endswith("/eslint-plugin"):
            # ESLint names a scoped plugin by its scope: "plugin:@x/...", rules "@x/rule"
            scope = name.split("/")[0]
            if scope + "/" in mention_text and re.search(
                    r"(?<![\w@-])" + re.escape(scope) + r"/(?!eslint-plugin\b)", mention_text):
                return True
        if name.startswith("expo-") and "expo" in runtime and ("expo" in specs or _mentions(mention_text, "expo")):
            return True  # Expo autolinks every expo-* module the app lists
        if "/" not in name and name in tool_cfg:
            return True
        if name == "critters" and "optimizeCss" in mention_text:
            return True  # Next loads critters itself when optimizeCss is on
        return any(name.startswith(pre) and any(x in specs or x in mention_text for x in users)
                   for pre, users in PAIRED_PREFIX.items())

    names = [n for n in runtime if isinstance(n, str)]
    is_used = {n: direct(n) for n in names}
    dev = man.get("devDependencies") if isinstance(man.get("devDependencies"), dict) else {}
    # a dev tool the app names (a Babel preset in a config): what the lockfile says it needs counts as used too
    dev_used = {n for n in dev if isinstance(n, str) and n not in is_used and direct(n)}
    graph = {}
    for k in range(len(app), -1, -1):  # lockfiles in the app folder and every folder above it
        for info in state.locks.get(tuple(app[:k]), ()):
            for pk, deps in info["graph"].items():
                graph.setdefault(pk, set()).update(deps)
    lock_used = set()
    while True:  # pairs and lockfile needs, followed from every used package, until nothing changes
        _k3_tick(state)
        used_names = {n for n, u in is_used.items() if u} | dev_used | specs | normed_used
        todo = [x for x in used_names if x in graph and x not in lock_used]
        reached = set(todo)
        while todo:
            for dep in graph.get(todo.pop(), ()):
                if dep not in reached:
                    reached.add(dep)
                    todo.append(dep)
        lock_used |= reached
        changed = False
        for n in names:
            if not is_used[n] and (any(p in used_names for p in PAIRED_WITH.get(n, ())) or n in lock_used):
                is_used[n] = changed = True
        if not changed:
            return lambda n: is_used.get(n, False)


def _several_ways(state, files, app_name, job, libs, alias):
    """One finding when two or more of libs are each used in at least one of files, else None."""
    is_py = libs[0] in PY_LIBS
    uses = {}  # library -> {file: first line}
    for f in files:
        for imp, line in state.imports.get(f, ()):
            if isinstance(imp, tuple):
                lib = imp[1] if is_py and imp[1] in libs and not (imp[1] == "aiohttp" and imp[2]) else None
            elif not is_py:
                lib = next((x for x in list(libs) + list(alias) if imp == x or imp.startswith(x + "/")), None)
                lib = alias.get(lib, lib)
            else:
                lib = None
            if lib and f not in uses.setdefault(lib, {}):
                uses[lib][f] = line
    used = sorted((x for x in libs if uses.get(x)), key=lambda x: (-len(uses[x]), min(uses[x])))
    if len(used) < 2:
        return None
    places = [{"path": min(uses[x]), "line": uses[x][min(uses[x])], "name": x} for x in used[:MAX_WARN_PLACES]]
    if any(safe_rel(p["path"].split("/")) is None for p in places):
        return None  # a path that is not safe to print (E13): the finding is dropped, never printed
    return {"kind": "several-ways", "app": app_name, "job": job, "count": len(used), "places": places,
            "more": max(0, len(used) - MAX_WARN_PLACES)}


def build_warnings(state):
    several, unused, coverage = warn_findings(state)
    findings = several + unused
    ordered = several[:MAX_K1_FINDINGS] + unused
    listed = ordered if state.uncapped else ordered[:MAX_WARNINGS]
    result = {
        "ok": True,
        "section": "warnings",
        "partial": bool(state.reasons),
        "version": __version__,
        "coverage": coverage,
        "partial_reasons": list(state.reasons),
        "stats": dict(state.stats, files_read=state.files_read),
        "findings": listed,
        "totals": {"findings": len(findings), "listed": len(listed), "not_listed": len(findings) - len(listed)},
    }
    return result  # at most 6 findings and 50 apps: always under MAX_OUTPUT_BYTES (test_worst_case_fits)


VOCABULARY = frozenset(VOCABULARY_CENSUS + SECTIONS + SIGNALS + FACTS + ADVICE + COVERAGE + ARCH_KINDS + APP_KINDS
                       + ARCH_REASONS)
PAY_VOCABULARY = VOCABULARY | frozenset(PAY_WHERE + SIGNATURE + PAID_FIELDS + PAID_TABLES + CLIENT_FIELDS)
WARN_VOCABULARY = VOCABULARY | frozenset(WARN_KINDS + WARN_JOBS + WARN_COVERAGE + WARN_K3_STATES + WARN_REASONS
                                         + tuple(lib for libs in JOB_FAMILIES.values() for lib in libs))


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
    whole = [h for h in state.hints if h[1]][:MAX_STOPLINE_HINTS]
    one_word = [h for h in state.hints if not h[1]][:MAX_STOPLINE_HINTS - len(whole)]
    capped = [state.hints_capped or len(whole) + len(one_word) < len(state.hints)]
    warnings_ = []

    def hint_list():
        warnings_[:] = ["stopline-hints-capped"] if capped[0] else []
        return [h[2] for h in sorted(whole + one_word)]

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
            "stopline_hints": hint_list(),
            "candidates": [c for t in TYPES for c in candidates[t]],
            "totals": totals,
        }

    result = render()
    if uncapped:
        return dict(result, demo_keys=list(state.demo_keys), demo_keys_trimmed=state.demo_keys_capped)
    while len(dumps(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        if one_word:  # new hints main never listed go before any candidate main kept
            one_word.pop()
            capped[0] = True
            result = render()
            continue
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
        if args.section == "warnings":
            state = WarnState(opts)
            state.uncapped = args.uncapped
            try:
                walk(repo, state)
                emit(build_warnings(state))
            except Exception:
                emit(envelope("internal-warnings"))  # its own code and hint, never the census one (X3)
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
