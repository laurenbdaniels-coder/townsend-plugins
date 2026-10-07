#!/usr/bin/env python3
"""custody_scan.py: read-only evidence gatherer for the eleven custody questions.

Runs on python 3.9+ with the standard library only. Reads a repository (never
its instruction files), never writes, never talks to the network, and prints one
JSON line whose strings have all been through a redaction sweep. Exit code 0
always, unless --exit-code is given.

Run it from the folder that CONTAINS the app:  python3 -I custody_scan.py --repo ./my-app

0.3.3 is 0.3.2 plus an overlay. 0.3.2's scanner (custody_scan_0_3_2.py, a byte-for-byte copy of the release,
checked against RELEASE_SHA256) runs first and alone; the overlay's checks run after it and can only make an
answer more cautious:

    --repo ──► load_release (sha-pinned, never via sys.path, no .pyc)
                 │
                 ▼
    release.run_scan + build_result ──► R  (0.3.2's answers, rows, partial flag, stats, output size)
                 │ deep copy R'
                 ▼
    overlay_pass (own walk, own reads, scratch states; time ≤ 2 × 0.3.2's, ≥ OVERLAY_MIN_S, ≤ 80% of the deadline)
                 │ Findings: rows per question (effect no | caution), gaps, finished / unfinished / error
                 ▼
    merge(R', Findings): answer = most cautious of 0.3.2's and the overlay's (No > Don't know > Nothing found);
                 0.3.2's rows first, overlay rows after them and trimmed first; never partial; never over the cap
                 │ (any error here: R' with Nothing found withheld, see fallback)
                 ▼
    stdout JSON, stderr summary "…; checks 0.3.3: finished|unfinished|error|skipped, N ms"

CUSTODY_CHECK_OVERLAY=0 skips the overlay: the output is 0.3.2's with only `version` changed.
"""
import sys

__version__ = "0.3.3"

_DOCS = "README.md#when-it-goes-wrong"
_PY_TOO_OLD = ("This scanner needs python 3.9 or newer. Run python3 --version; on macOS install the Command Line Tools, on Windows use py -3.", _DOCS)


def version_guard(version_info):
    """Return a failure envelope when the interpreter is too old, else None (0.3.2's guard and wording)."""
    if tuple(version_info[:2]) < (3, 9):
        hint, docs = _PY_TOO_OLD
        return {"ok": False, "error": "python-too-old", "hint": hint, "docs": docs, "partial": True}
    return None


_guard = version_guard(sys.version_info)
if _guard is not None and __name__ == "__main__":
    import json as _json
    sys.stdout.write(_json.dumps(_guard, separators=(",", ":")) + "\n")
    sys.exit(0)

import bisect
import collections
import copy
import hashlib
import json
import os
import re
import stat
import string
import time
import types
import warnings

# ------------------------------------------------------------------ the release, loaded by hash

RELEASE_FILE = "custody_scan_0_3_2.py"
RELEASE_SHA256 = "0ff12f55bd723fc70981741bc400b606ea315750796d7009d0e0d3365ab9c8d6"  # of the text with \r\n read as \n
_RELEASE_HINT = "A custody-check file is missing or changed; reinstall the plugin, or re-run the cp -R command in README step 1."


class ReleaseUnavailable(Exception):
    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code


def load_release(path=None):
    """Load 0.3.2 from its file next to this one, without the import system: the bytes are checked against
    RELEASE_SHA256 (line endings normalised, so a Windows checkout loads), compiled and executed into a fresh
    module. Nothing is written (no .pyc) and nothing on sys.path can stand in for it."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), RELEASE_FILE)
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        raise ReleaseUnavailable("internal:release-missing")
    data = data.replace(b"\r\n", b"\n")
    if hashlib.sha256(data).hexdigest() != RELEASE_SHA256:
        raise ReleaseUnavailable("internal:release-modified")
    module = types.ModuleType("custody_scan_0_3_2")
    module.__file__ = path
    try:
        exec(compile(data.decode("utf-8"), path, "exec"), module.__dict__)
    except SystemExit:
        raise
    except Exception:
        raise ReleaseUnavailable("internal:release-modified")
    return module


def release_envelope(code):
    return {"ok": False, "error": code, "hint": _RELEASE_HINT, "docs": _DOCS, "partial": True}


try:
    release = load_release()
    RELEASE_ERROR = None
except ReleaseUnavailable as _exc:
    release = None
    RELEASE_ERROR = _exc.code

# ------------------------------------------------------------------ overlay constants

OVERLAY_MIN_S = 5.0  # the overlay's least time; a longer --deadline-s raises it (deadline / 24)
OVERLAY_SHARE_OF_DEADLINE = 0.8  # the whole scan ends by this share of --deadline-s, so a host's own timeout never kills it
QS = ("q1", "q3", "q9")
RANK = {"nothing-found": 0, "dont-know": 1, "no": 2}
UNFINISHED_SNIPPETS = {"unfinished": "time ran out; rerun with --deadline-s 600",
                       "error": "an error; please report it"}  # each row shorter than any nothing-found row it replaces

# check id -> the questions its rows go to. Every overlay row is evidence; the one No is a key in browser-side
# .mts/.cts code (source "mts-key"), read with 0.3.2's own key detectors.
OVERLAY_CHECKS = {
    "mcp-config-not-opened": ("q1",), "code-file-not-read": ("q1",),
    "open-rule-unconfirmed": ("q3",), "open-rule-in-string": ("q3",), "policy-true-unevaluated": ("q3",),
    "firebase-rules-test-mode": ("q3",), "firebase-rules-true-unevaluated": ("q3",), "public-view": ("q3",),
    "rules-not-read-whole": ("q3",), "table-dropped": ("q3",), "no-rule-statements": ("q3",),
    "manifest-not-parsed": ("q9",),
    "compressed-file-not-read": ("q1", "q3", "q9"), "checks-not-finished": ("q1", "q3", "q9"),
}
CAPPED_PER_SCAN = {"mcp-config-not-opened", "manifest-not-parsed", "compressed-file-not-read", "code-file-not-read"}
REUSED_CHECKS = ("policy-with-check-true", "policy-to-anon", "storage-bucket-public-sql", "firebase-rules-public-read",
                 "table-without-rls", "policy-select-true", "policy-altered-true", "cron-schedule", "monitoring-dependency",
                 "health-route")  # plus every 0.3.2 Q1 id, from the .mts key read



def all_checks():
    """Every check id the output can hold: 0.3.2's (question, effect) and the overlay's, as {id: (questions, effect)}."""
    out = dict((k, ((q,), e)) for k, (q, e) in release.CHECKS.items())
    out.update((k, (qs, "evidence")) for k, qs in OVERLAY_CHECKS.items())
    return out


MCP_CHECK = "mcp-config-not-opened"
NEVER_OPEN_MCP_PATHS = {".kiro": ("settings/mcp.json",), ".amazonq": ("cli-agents",), ".gemini": ("settings.json",),
                        ".continue": ("config.json", "config.yaml"), ".codex": ("config.toml",)}  # configs whose names do not say mcp
NEVER_OPEN_MCP_NAME_RE = re.compile(r"mcp", re.I)  # any file or folder with mcp in its name inside a never-open agent folder
MCP_DOC_FILE_RE = re.compile(r"\.(?:md|mdc|markdown)$", re.I)  # instructions or notes about MCP, not a config
MCP_CONFIG_FILE_RE = re.compile(r"\.(?:jsonc?|ya?ml|toml|env)$", re.I)  # config-shaped, whatever its name
MCP_DOC_PARENTS = {"skills", "rules", "instructions", "prompts", "agents", "commands"}  # folders of instructions, never reported by name
NEVER_OPEN_SECRET_FILE_RE = re.compile(r"^(?:opencode\.jsonc?|\.aider[^/]*\.ya?ml)$", re.I)  # agent configs that carry MCP servers or API keys
COMPRESSED_EXTS = (".zst", ".zstd")  # 0.3.2 read these as text; the overlay names what they could hide
MODULE_EXTS = (".mts", ".cts")  # TypeScript modules 0.3.2 did not read as code
NESTED_DETAIL = "condition nested too deeply to evaluate (%d chars); review it by hand"

RLS_DISABLED_RE = re.compile(r"disable\s+row\s+level\s+security", re.I)
USING_TRUE_RE = re.compile(r"\busing\s*\((?:\s*\()*\s*true(?:\s*::\s*bool(?:ean)?)?(?:\s*\))+", re.I)  # any depth: using (((true)))
WITH_CHECK_TRUE_RE = re.compile(r"\bwith\s+check\s*\(\s*true\s*\)", re.I)
POLICY_SELECT_RE = re.compile(r"\bfor\s+select\b", re.I)
MAX_PREDICATE_CHARS = 4000
PAREN_RE = re.compile(r"[()]")
OR_SPLIT_RE = re.compile(r"[()\[\]]|\|\||\?")  # `?` for the ternary, which binds looser than ||; [ ] nest like ( )
FIREBASE_STRING_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')  # a rules string literal, escapes included
SQL_BOOL_CAST_RE = re.compile(r"\s*::\s*bool(?:ean)?\b")
SQL_OR_RE = re.compile(r"\bor\b")
SQL_AND_RE = re.compile(r"\band\b")
WHITESPACE_RE = re.compile(r"\s+")
# The specification _firebase_ifs implements without reading up to 400 characters per `allow` (the tests compare them):
FIREBASE_IF_RE = re.compile(r"\ballow\s{1,20}([a-z]+(?:\s{0,20},\s{0,20}[a-z]+){0,10})\s{0,20}:\s{0,20}if(?=[\s(])(?=((?:[^;}\n]|\n(?![ \t]{0,80}(?:allow|match)\b)){0,400}))\2(?=[;}]|\n[ \t]{0,80}(?:allow|match)\b)", re.I)
FIREBASE_IF_LONG_RE = re.compile(r"\ballow\s{1,20}[a-z]+(?:\s{0,20},\s{0,20}[a-z]+){0,10}\s{0,20}:\s{0,20}if(?=[\s(])(?:[^;}\n]|\n(?![ \t]{0,80}(?:allow|match)\b)){401}", re.I)  # past what FIREBASE_IF_RE reads
FIREBASE_IF_HEAD_RE = re.compile(r"\ballow\s{1,20}([a-z]+(?:\s{0,20},\s{0,20}[a-z]+){0,10})\s{0,20}:\s{0,20}if(?=[\s(])", re.I)
FIREBASE_IF_END_RE = re.compile(r"[;}]|\n(?=[ \t]{0,80}(?:allow|match)\b)", re.I)
MAX_FIREBASE_CONDITION = 400
TRUE_TOKEN_RE = re.compile(r"(?<![\w.])true(?![\w.])")
FIREBASE_TEST_MODE_RE = re.compile(r"\ballow\s{1,20}[a-z]+(?:\s{0,20},\s{0,20}[a-z]+){0,10}\s{0,20}:\s{0,20}if(?=[\s(])\s{0,20}(?:\(\s{0,20})*(?:request\.time\s{0,20}<|timestamp\.date\([^)\n]{0,40}\)\s{0,20}>\s{0,20}request\.time)", re.I)
RTDB_TEST_MODE_RE = re.compile(r"\"\.(?:read|write)\"\s{0,20}:\s{0,20}\"\s{0,5}now\s{0,5}<", re.I)
RTDB_WRITE_OPEN_RE = re.compile(r"\"\.write\"\s{0,20}:\s{0,20}(?:true|\"\s{0,5}true\s{0,5}\")", re.I)  # "true" as a string rule is the same rule
RTDB_READ_OPEN_RE = re.compile(r"\"\.read\"\s{0,20}:\s{0,20}(?:true|\"\s{0,5}true\s{0,5}\")", re.I)
MONITORING_DEPS = {"elastic-apm-node", "logrocket", "logfire", "appsignal", "skylight", "ddtrace", "elastic-apm",
                   "github.com/datadog/dd-trace-go", "gopkg.in/datadog/dd-trace-go"}  # names 0.3.2's list did not hold
# whole vendor scopes and families: @sentry/vue, @opentelemetry/api, opentelemetry-sdk are error tracking or tracing whatever the suffix
MONITORING_PREFIXES = ("@sentry/", "@bugsnag/", "@opentelemetry/", "@datadog/", "@honeybadger-io/", "@rollbar/", "@logtail/", "@highlight-run/", "@appsignal/", "opentelemetry-")
GO_DOT_MAJOR_RE = re.compile(r"\.v[0-9]+$")  # gopkg.in/DataDog/dd-trace-go.v1 is dd-trace-go (0.3.2 strips /vN only)
_SQL_IDENT = r"(?:\"[^\"\n]{1,63}\"|[A-Za-z_][A-Za-z0-9_$]{0,62})"
_SQL_TABLE = "(" + _SQL_IDENT + r"(?:\s*\.\s*" + _SQL_IDENT + ")?)"  # optionally schema-qualified
_CREATE_TABLE_HEAD = r"\bcreate\s+(?:(?:unlogged|foreign)\s+)?table"
CREATE_TABLE_RE = re.compile(_CREATE_TABLE_HEAD + r"\s+(?:if\s+not\s+exists\s+)?" + _SQL_TABLE, re.I)
ENABLE_RLS_RE = re.compile(r"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?" + _SQL_TABLE + r"\s+enable\s+row\s+level\s+security", re.I)
MAX_DROP_LIST_CHARS = 20000
DROP_TABLE_RE = re.compile(r"\bdrop\s+table\s+(?:if\s+exists\s+)?([^;]{1,%d})" % MAX_DROP_LIST_CHARS, re.I)
DROP_ITEM_RE = re.compile(r"\s{0,20}" + _SQL_TABLE)
CREATE_VIEW_RE = re.compile(r"\bcreate\s+(?:or\s+replace\s+)?(?:recursive\s+)?(materialized\s+)?view\s+(?:if\s+not\s+exists\s+)?" + _SQL_TABLE + r"([^;]{0,400})", re.I)
SQL_LEX_OPENER_RE = re.compile(r"--|/\*|\"|(?<![A-Za-z0-9_])[Ee]'|'|\$(?:[^\W\d]\w{0,30})?\$")  # whichever comes first; a dollar tag may use any letter
SQL_PLAIN_BODY_RE = re.compile(r"(?:[^']|'')*'")  # a SQL string may span lines
SQL_ESCAPE_BODY_RE = re.compile(r"(?:[^'\\]|\\[\s\S]|'')*'")
SQL_IDENT_BODY_RE = re.compile(r'(?:[^"]|"")*"')  # a quoted identifier: "o'brien_idx" holds no string
MAX_DO_NESTING = 8
DO_BEFORE_RE = re.compile(r"\bdo(?:\s{1,20}language\s{1,20}[A-Za-z_][A-Za-z0-9_]{0,30})?\s{0,20}$", re.I)  # DO $$ … or DO LANGUAGE plpgsql $$ …
SAFE_INVOKER_RE = re.compile(r"\bsecurity_invoker\s{0,20}(?:=\s{0,20}'?(?:on|true|1|yes)\b|(?=\s{0,20}[,)]))", re.I)
VIEW_AS_RE = re.compile(r"\bas\b", re.I)
VIEW_WITH_RE = re.compile(r"\bwith\s*\(([^)]{0,400})\)", re.I)
RULE_SQL_RE = re.compile(_CREATE_TABLE_HEAD + r"\b|\bcreate\s+policy\b|\brow\s+level\s+security\b|\bstorage\.buckets\b", re.I)
UNPARSED_MANIFEST_RE = re.compile(r"^(?:pipfile|setup\.py|setup\.cfg|composer\.json|cargo\.toml|pom\.xml|build\.gradle(?:\.kts)?|pubspec\.yaml|deno\.jsonc?|import_map\.json|environment\.ya?ml|mix\.exs|[^/]+\.csproj|[^/]+\.gemspec"
                                  r"|requirements(?:[-_.][^/]+)?\.in|requirements[-_.][^/]+\.txt|[^/]+[-_]requirements\.(?:txt|in))$")
NOT_NEWLINE_RE = re.compile(r"[^\n]")
ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)  # keeps every offset, unlike str.lower ("İ")

McpScan = collections.namedtuple("McpScan", "found truncated")


class OverlayTimeout(Exception):
    """The overlay's time ran out between files."""


# ------------------------------------------------------------------ findings

class Overlay(object):
    """What the overlay found: rows per question (each with its effect and source), gaps, and how the pass ended.
    tick() is the in-file deadline check, on the real monotonic clock like 0.3.2's ScanState.tick."""

    def __init__(self, deadline):
        self.deadline = deadline
        self.ticks = 0
        self.rows = dict((q, []) for q in QS)
        self.more = dict((q, 0) for q in QS)  # rows past the per-question cap: counted, not kept
        self.gaps = dict((q, 0) for q in QS)
        self.keys = set()
        self.tables = {}  # public table -> (path, line), only tables 0.3.2 did not register
        self.rls_enabled = set()
        self.rule_files = 0
        self.status = "finished"
        self.stopped_by = None  # "clock" (between files) or "tick" (inside a file), for the tests
        self.named = {}  # rows per name-only check: five name the files, the gap counts every one

    @property
    def finished(self):
        return self.status == "finished"

    def tick(self):
        self.ticks += 1
        if self.ticks % release.DEADLINE_TICK == 0 and time.monotonic() > self.deadline:
            self.stopped_by = "tick"
            raise release.Deadline()

    def add(self, check, path, line, snippet, effect="caution", source="names", gap=False, questions=None):
        if questions is None:
            questions = OVERLAY_CHECKS[check] if check in OVERLAY_CHECKS else (release.CHECKS[check][0],)
        row = {"path": release.sanitize_path(path), "line": int(line), "snippet": release.sanitize(snippet), "check": check}
        for q in questions:
            if q not in self.rows:
                continue
            if gap:
                self.gaps[q] += 1
            key = (q, check, row["path"], row["line"], row["snippet"])
            if key in self.keys:
                continue
            self.keys.add(key)
            if len(self.rows[q]) < 2 * release.MAX_EVIDENCE:
                self.rows[q].append(dict(row, _effect=effect, _source=source))
            else:
                self.more[q] += 1

    def gap(self, check, path, line=0, snippet="", questions=None):
        """A thing the overlay could not look at: a named row, so no gap shows as a bare summary row. Name-only
        checks (an agent folder's configs, unparsed manifests) name five files per scan; the gap counts all."""
        if check in CAPPED_PER_SCAN:
            self.named[check] = self.named.get(check, 0) + 1
            if self.named[check] > release.MAX_HITS_PER_FILE_PER_CHECK:
                for q in (questions or OVERLAY_CHECKS[check]):
                    self.gaps[q] += 1
                return
        self.add(check, path, line, snippet, gap=True, questions=questions)


class OverlayFile(object):
    __slots__ = ("rel", "base", "ext", "text", "_lex")

    def __init__(self, rel, base, ext, text):
        self.rel, self.base, self.ext, self.text = rel, base, ext, text
        self._lex = None

    def sql_lex(self):
        if self._lex is None:
            self._lex = _lex_sql(self.text)
        return self._lex


def _clause(m):
    return m.group(0)[:release.MAX_SNIPPET]


def _finditer_rows(regex, text, sf, ov, check, counter):
    for m in regex.finditer(text):
        ov.tick()
        if not release._cap(counter, check):
            break
        ov.add(check, sf.rel, release.line_of(text, m.start()), _clause(m), source="sql")

# ------------------------------------------------------------------ SQL

def _blank(chunk):
    return NOT_NEWLINE_RE.sub(" ", chunk) if "\n" in chunk else " " * len(chunk)


def _lex_sql(text, depth=0, tick=None):
    """Read SQL once, left to right, taking whichever of `--`, `/* */`, a quoted identifier, '…', E'…' or
    $tag$…$tag$ comes first. Returns (no_comments, code, bare, unclosed), every copy at the same offsets as
    `text`: `no_comments` keeps strings, `code` blanks them, `bare` also blanks quoted identifiers. A DO block's
    body runs, so it is lexed in place; a function body only runs when called, so it is a string. An unclosed
    quote or dollar tag blanks the rest of `code` and sets `unclosed`; an unclosed /* stays visible."""
    nc, code, bare = [], [], []
    pos = 0
    n = len(text)
    unclosed = False
    no_block_close = False

    def emit(raw, in_code, in_bare):
        nc.append(raw)
        code.append(in_code)
        bare.append(in_bare)

    while pos < n:
        if tick is not None:
            tick()
        m = SQL_LEX_OPENER_RE.search(text, pos)
        if not m:
            break
        tok = m.group(0)
        plain = text[pos:m.start()]
        emit(plain, plain, plain)
        stop = None  # where the token ends; stays None when it never closes
        if tok == "--":
            stop = text.find("\n", m.start())
            stop = n if stop < 0 else stop
            gap = _blank(text[m.start():stop])
            emit(gap, gap, gap)
        elif tok == "/*":
            k = -1 if no_block_close else text.find("*/", m.end())  # the first */ closes, as in 0.3.2
            if k < 0:
                no_block_close = True  # no */ anywhere after this: later openers skip the search, keeping one pass
                emit(tok, tok, tok)
                pos = m.end()
                continue
            stop = k + 2
            gap = _blank(text[m.start():stop])
            emit(gap, gap, gap)
        elif tok == '"':
            body = SQL_IDENT_BODY_RE.match(text, m.end())
            if body:
                stop = body.end()
                if "\n" in text[m.start():stop]:
                    emit(tok, tok, tok)  # a real name never spans lines: this quote is just a character, so read on
                    pos = m.end()
                    continue
                name = text[m.start():stop]
                emit(name, name, _blank(name))
        elif tok.startswith("$"):
            close = text.find(tok, m.end())
            if close >= 0:
                stop = close + len(tok)
                if depth < MAX_DO_NESTING and DO_BEFORE_RE.search(text, max(0, m.start() - 40), m.start()):
                    inner_nc, inner_code, inner_bare, inner_unclosed = _lex_sql(text[m.end():close], depth + 1, tick)
                    unclosed = unclosed or inner_unclosed
                    emit(tok + inner_nc + tok, tok + inner_code + tok, tok + inner_bare + tok)
                else:
                    body = text[m.start():stop]
                    gap = _blank(body)
                    emit(body, gap, gap)
        else:
            body = (SQL_ESCAPE_BODY_RE if tok[0] in "Ee" else SQL_PLAIN_BODY_RE).match(text, m.end())
            if body:
                stop = body.end()
                chunk = text[m.start():stop]
                gap = _blank(chunk)
                emit(chunk, gap, gap)
        if stop is None:
            unclosed = True  # a quote, name or tag that never closes: nothing after it can be read as code
            rest = text[m.start():]
            gap = _blank(rest)
            emit(rest, gap, gap)
            pos = n
            break
        pos = stop
    plain = text[pos:]
    emit(plain, plain, plain)
    return "".join(nc), "".join(code), "".join(bare), unclosed


def _paren_closes(text):
    """Each '(' offset mapped to the offset of the ')' that brings the level back down: one pass, linear."""
    closes, stack = {}, []
    for m in PAREN_RE.finditer(text):
        if m.group(0) == "(":
            stack.append(m.start())
        elif stack:
            closes[stack.pop()] = m.start()
    return closes


def _sql_predicate_open(text, start, closes, budget, rec_budget=None):
    """Whether the `using (…)` group that starts at `start` is open: `true`, `true or …`, `(true)::bool`, read
    with the same top-level ||/&& rule as a Firebase condition. A group that does not close within
    MAX_PREDICATE_CHARS is not open; `budget` caps the characters read across the file. `text` is the file with
    strings, comments and quoted names blanked, so `or true` inside a string is never an operand."""
    open_at = text.find("(", start)
    close = closes.get(open_at)
    if close is None or close - open_at >= MAX_PREDICATE_CHARS or budget["left"] < close - open_at:
        return False
    budget["left"] -= close - open_at
    expr = SQL_BOOL_CAST_RE.sub("", text[open_at:close + 1].lower()).replace("||", "+")  # SQL || joins strings, it is not OR
    expr = SQL_OR_RE.sub("||", SQL_AND_RE.sub("&&", expr))
    return _firebase_open(WHITESPACE_RE.sub("", expr), 0, rec_budget)


def _policy_kind(low, lo, s):
    """The FOR clause of the policy a `using (true)` at s belongs to, read from `low` (the ASCII-lowered,
    quote-blanked file) between lo and s, by position: nothing is copied per match."""
    cp = low.rfind("create policy", lo, s)
    ap = low.rfind("alter policy", lo, s)
    if ap > cp:
        return "policy-altered-true"
    if cp >= 0 and POLICY_SELECT_RE.search(low, cp, s):
        return "policy-select-true"
    return "policy-using-true"


def _in_code(m, bare):
    """The whole match is code: not inside a string, a comment or a quoted name."""
    return bare[m.start():m.end()] == m.group(0)


def _caution(check):
    """Every Q3 No comes from 0.3.2. A rule the overlay calls open is evidence, never a new No."""
    return "open-rule-unconfirmed" if release.CHECKS.get(check, ("", ""))[1] == "no" else check


def detect_sql(sf, ov, rel_state):
    counter = {}
    text, code, bare, unclosed = _lex_sql(sf.text, tick=ov.tick)
    if RULE_SQL_RE.search(code):
        ov.rule_files += 1
    if unclosed:
        ov.gap("rules-not-read-whole", sf.rel, 0, "a quote or $tag$ that never closes")
    low = bare.translate(ASCII_LOWER)
    closes, budget = None, {"left": len(text) + MAX_PREDICATE_CHARS}
    for m in RLS_DISABLED_RE.finditer(text):
        ov.tick()
        check = "open-rule-unconfirmed" if _in_code(m, bare) else "open-rule-in-string"
        if release._cap(counter, check):
            ov.add(check, sf.rel, release.line_of(text, m.start()), _clause(m), source="sql")
    for m in USING_TRUE_RE.finditer(text):
        ov.tick()
        check = _policy_kind(low, max(0, m.start() - 2000), m.start())
        rec = {}
        if not release.USING_TRUE_RE.match(text, m.start()):
            if closes is None:
                closes = _paren_closes(bare)  # only when a group needs reading; parens in strings do not count
            if not _sql_predicate_open(bare, m.start(), closes, budget, rec):
                check = "policy-true-unevaluated"
        check = _caution(check) if _in_code(m, bare) else "open-rule-in-string"
        if release._cap(counter, check):
            nested = check == "policy-true-unevaluated" and rec.get("exhausted")
            ov.add(check, sf.rel, release.line_of(text, m.start()), NESTED_DETAIL % rec["chars"] if nested else _clause(m), source="sql")
    _finditer_rows(WITH_CHECK_TRUE_RE, text, sf, ov, "policy-with-check-true", counter)
    _finditer_rows(release.POLICY_TO_ANON_RE, text, sf, ov, "policy-to-anon", counter)
    _finditer_rows(release.STORAGE_BUCKET_TRUE_RE, text, sf, ov, "storage-bucket-public-sql", counter)
    _finditer_rows(release.CRON_SQL_RE, text, sf, ov, "cron-schedule", counter)
    pos, line = 0, 1
    for n, m in enumerate(CREATE_TABLE_RE.finditer(text)):
        if n >= release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, 0, "more create table statements than the scanner reads")
            break
        ov.tick()
        line += text.count("\n", pos, m.start())
        pos = m.start()
        name = release._public_table(m.group(1))
        if name and name not in rel_state.tables and name not in ov.tables and len(ov.tables) < release.MAX_SEEN:
            ov.tables[name] = (sf.rel, line)
    enabled_at = {}  # public table -> offset of its last `enable row level security` in this file
    for n, m in enumerate(ENABLE_RLS_RE.finditer(code)):
        if n >= release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, 0, "more enable row level security statements than the scanner reads")
            break
        ov.tick()
        if bare[m.start():m.start(1)] != code[m.start():m.start(1)] or bare[m.end(1):m.end()] != code[m.end(1):m.end()]:
            continue  # `create index "alter table t enable row level security"` names an index; it enables nothing
        name = release._public_table(m.group(1))
        if name:
            enabled_at[name] = m.start()
            if len(ov.rls_enabled) < release.MAX_SEEN:
                ov.rls_enabled.add(name)  # credit for the overlay's own tables only; 0.3.2's credit is its own
    for n, m in enumerate(DROP_TABLE_RE.finditer(text)):
        if n >= release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, 0, "more drop table statements than the scanner reads")
            break
        ov.tick()
        parts = m.group(1).split(",")
        if len(m.group(1)) >= MAX_DROP_LIST_CHARS or len(parts) > release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, release.line_of(text, m.start()), "a drop list too long to read whole")
        for part in parts[:release.MAX_TABLE_MATCHES_PER_FILE]:
            t = DROP_ITEM_RE.match(part)
            name = release._public_table(t.group(1)) if t else None
            # a table dropped and made again loses its RLS; unless this file turns it back on afterwards, migration
            # order across files decides, and the scanner does not replay migrations
            if name and enabled_at.get(name, -1) < m.start():
                ov.gap("table-dropped", sf.rel, release.line_of(text, m.start()), name)
    counter_views = {}
    for m in CREATE_VIEW_RE.finditer(text):
        ov.tick()
        name = release._public_table(m.group(2))
        # a view runs as its owner and skips the table's RLS unless security_invoker is set; a materialized view has no RLS at all
        head = VIEW_AS_RE.split(m.group(3), 1)[0]
        options = " ".join(w.group(1) + ")" for w in VIEW_WITH_RE.finditer(head))
        if name and (m.group(1) or not SAFE_INVOKER_RE.search(options)) and release._cap(counter_views, "public-view"):
            ov.add("public-view", sf.rel, release.line_of(text, m.start()), name, source="sql")

# ------------------------------------------------------------------ Firebase rules

def _rec_budget(rec_budget, expr):
    """The recursion budget for one condition, in characters handed to `_firebase_open`: 4 x the condition + 200."""
    if rec_budget is None:
        rec_budget = {}
    if "left" not in rec_budget:
        rec_budget["left"] = 4 * len(expr) + 200
        rec_budget["chars"] = len(expr)
    return rec_budget


def _charge(rec_budget, n):
    if rec_budget["left"] < n:
        rec_budget["exhausted"] = True
        return False
    rec_budget["left"] -= n
    return True


def _firebase_condition(cond, rec_budget=None):
    """"open" when the condition is `true`, or has a top-level `||` operand that is `true`, with fully
    parenthesised groups read the same way; "unevaluated" when `true` appears in anything else; None when
    `true` is not there at all. Text inside a rules string is never an operand."""
    if not TRUE_TOKEN_RE.search(cond):
        return None
    code = FIREBASE_STRING_RE.sub(lambda m: "_" * len(m.group(0)), cond)
    if '"' in code or "'" in code:
        return "unevaluated"  # a quote that never closes: what follows it could not be read as code
    if not TRUE_TOKEN_RE.search(code):
        return None  # `true` only inside a string (`visibility == "true"`)
    return "open" if _firebase_open(WHITESPACE_RE.sub("", code), 0, rec_budget) else "unevaluated"


def _firebase_open(expr, depth, rec_budget=None):
    """Whether expr is open (see `_firebase_condition`). rec_budget is shared by every call below this one; when it
    runs out the answer is "not open", never "open"."""
    rec_budget = _rec_budget(rec_budget, expr)
    if not _charge(rec_budget, len(expr)):
        return False
    expr = _strip_outer_parens(expr)
    if expr == "true":
        return True
    if depth > 20:
        return False
    parts, level, last = [], 0, 0
    for m in OR_SPLIT_RE.finditer(expr):  # parens and top-level ||, found by the regex engine, not char by char
        tok = m.group(0)
        if tok in "([":
            level += 1
        elif tok in ")]":
            level -= 1
        elif level == 0 and tok == "?":
            return False  # `a ? b : c || true` is open only when a holds: not worked out here
        elif level == 0:
            parts.append(expr[last:m.start()])
            last = m.end()
    parts.append(expr[last:])
    if len(parts) == 1:
        return False  # one operand that is not `true` itself: `true && x`, `!(…)`, `x == (…)`, `f(…)`
    # cheapest operand first, so a short `|| true` is reached before a deep operand spends the budget; ordered by
    # length buckets, not a sort, so the work stays linear in the characters this call was charged for
    buckets = {}
    for part in parts:
        buckets.setdefault(len(part), []).append(part)
    return any(_firebase_open(part, depth + 1, rec_budget) for n in range(min(buckets), max(buckets) + 1) for part in buckets.get(n, ()))


def _strip_outer_parens(expr):
    """Drop the outer pairs that wrap the whole expression: `((a || b))` -> `a || b`, never `(a) || (b)`. Linear."""
    n = len(expr)
    k = 0
    while k < n - 1 - k and expr[k] == "(" and expr[n - 1 - k] == ")":
        k += 1  # candidate pairs: leading ( facing trailing )
    if not k:
        return expr
    levels, level = [], 0
    for c in expr:
        level += c == "("
        level -= c == ")"
        levels.append(level)
    lo, hi = k - 1, n - 1 - k
    window_min = min(levels[lo:hi]) if hi > lo else levels[lo]
    mins = [0] * k
    for j in range(k - 1, -1, -1):
        window_min = min(window_min, levels[j], levels[n - 2 - j])
        mins[j] = window_min
    j = 0
    while j < k and mins[j] > j:
        j += 1
    return expr[j:n - j]


class _FirebaseIf(object):
    """A rule head (group 1) and its condition (group 2), as detect_rules reads them."""
    __slots__ = ("text", "head", "end2")

    def __init__(self, text, head, end2):
        self.text, self.head, self.end2 = text, head, end2

    def start(self, g=0):
        return self.head.end() if g == 2 else self.head.start()

    def end(self, g=0):
        return self.end2

    def group(self, g=0):
        if g == 1:
            return self.head.group(1)
        return self.text[self.start(g):self.end2]


def _firebase_ifs(text, tick=None):
    """(conditions of at most MAX_FIREBASE_CONDITION characters, count of longer ones): a condition runs from the
    rule head to the first terminator after it (`;`, `}`, or a new line that starts another allow or match).
    Terminators are found once; each head finds its own with a bisect."""
    ends = [m.start() for m in FIREBASE_IF_END_RE.finditer(text)]
    found, long_n = [], 0
    next_if = next_long = 0
    for head in FIREBASE_IF_HEAD_RE.finditer(text):
        if tick is not None:
            tick()
        b = head.end()
        k = bisect.bisect_left(ends, b)
        e = ends[k] if k < len(ends) else None
        if head.start() >= next_if and e is not None and e - b <= MAX_FIREBASE_CONDITION:
            found.append(_FirebaseIf(text, head, e))
            next_if = e
        if head.start() >= next_long and (len(text) if e is None else e) - b > MAX_FIREBASE_CONDITION:
            long_n += 1
            next_long = b + MAX_FIREBASE_CONDITION + 1
    return found, long_n


def detect_rules(sf, ov):
    counter = {}
    ov.rule_files += 1
    # JSON rules files have no // comments, and a URL inside a string would eat the rest of the line
    text = release._blank_block_comments(sf.text) if sf.base.lower().endswith(".json") else release._strip_slash_comments(sf.text)
    ifs, long_n = _firebase_ifs(text, ov.tick)
    for m in ifs:
        ov.tick()
        rec = {}
        verdict = _firebase_condition(m.group(2), rec)
        if verdict == "open" and sf.text[m.start(2):m.end(2)] != m.group(2):
            verdict = "unevaluated"  # a `/*` or `//` inside the condition (often inside a string) was cut as a comment
        if verdict == "open":
            check = "open-rule-unconfirmed" if release.FIREBASE_WRITE_RE.search(m.group(1)) else "firebase-rules-public-read"
        elif verdict == "unevaluated":
            check = "firebase-rules-true-unevaluated"
        else:
            continue
        if release._cap(counter, check):
            nested = verdict == "unevaluated" and rec.get("exhausted")
            ov.add(check, sf.rel, release.line_of(text, m.start()), NESTED_DETAIL % rec["chars"] if nested else _clause(m), source="rules")
    for _ in range(long_n):
        ov.tick()
        ov.gap("rules-not-read-whole", sf.rel, 0, "a condition longer than the scanner reads")
    for regex in (FIREBASE_TEST_MODE_RE, RTDB_TEST_MODE_RE):
        for m in regex.finditer(text):
            ov.tick()
            if release._cap(counter, "firebase-rules-test-mode"):
                ov.add("firebase-rules-test-mode", sf.rel, release.line_of(text, m.start()), _clause(m), source="rules")
    for m in RTDB_WRITE_OPEN_RE.finditer(text):
        ov.tick()
        if release._cap(counter, "open-rule-unconfirmed"):
            ov.add("open-rule-unconfirmed", sf.rel, release.line_of(text, m.start()), _clause(m), source="rules")
    for m in RTDB_READ_OPEN_RE.finditer(text):
        ov.tick()
        if release._cap(counter, "firebase-rules-public-read"):
            ov.add("firebase-rules-public-read", sf.rel, release.line_of(text, m.start()), _clause(m), source="rules")

# ------------------------------------------------------------------ .mts / .cts, manifests

def _ts_name(name):
    return name[:-4] + ".ts"


def detect_module(sf, ov, opts):
    """A .mts/.cts file read as its .ts sibling would be (C52b): the same classification, so route.mts is server
    code like route.ts, and 0.3.2's own key detectors on a scratch state. Its Q1 rows, and a health route (Q9),
    are the overlay's; a key 0.3.2's rules call a No in browser code is the overlay's one No."""
    rel_ts, base_ts = _ts_name(sf.rel), _ts_name(sf.base)
    cls, kinds = release.classify(rel_ts, base_ts, ".ts", sf.text)
    rsf = release.ScanFile(rel_ts, base_ts, ".ts", cls, kinds, sf.text)
    scratch = release.ScanState()
    scratch.deadline = ov.deadline
    if release._q1_gate(rsf, opts):
        claimed = []
        release.detect_browser_prefix(rsf, scratch, opts, claimed)
        release.detect_key_literals(rsf, scratch, opts, claimed)
    if "PRIVATE KEY" in sf.text:
        release.detect_private_keys(rsf, scratch, opts)
    release.detect_model_hints(rsf, scratch, opts)
    ts_path = release.sanitize_path(rel_ts)
    for q, checks in (("q1", None), ("q9", ("health-route",))):
        for row in scratch.evidence[q]:
            if checks is not None and row["check"] not in checks:
                continue
            effect = "no" if release.CHECKS[row["check"]][1] == "no" else "caution"
            path = sf.rel if row["path"] == ts_path else row["path"]
            ov.add(row["check"], path, row["line"], row["snippet"], effect=effect, source="mts-key" if q == "q1" else "names", questions=(q,))
            # snippets were made by 0.3.2's make_snippet (redacted); add() sanitizes them again, which is idempotent


def detect_monitoring(sf, ov):
    """Error tracking 0.3.2's list did not name: vendor families (@sentry/vue, @opentelemetry/api) and a few
    more names. Dependencies are read with 0.3.2's own parser, on a scratch state."""
    scratch = release.ScanState()
    names, _ = release._read_dependencies(sf.base.lower(), sf.text, scratch)
    counter = {}
    for name in sorted(names):
        ov.tick()
        lname = name.lower()
        if lname in release.MONITORING_DEPS:
            continue  # 0.3.2 already named it
        stripped = GO_DOT_MAJOR_RE.sub("", lname)
        if (lname in MONITORING_DEPS or stripped in MONITORING_DEPS or lname.startswith(MONITORING_PREFIXES)) and release._cap(counter, "monitoring-dependency"):
            ov.add("monitoring-dependency", sf.rel, 0, name, source="manifest")

# ------------------------------------------------------------------ never-open agent folders (names only)

def _lexists_inside(path, inner):
    """Whether path/inner exists without following a symlink at any step."""
    for part in inner.split("/")[:-1]:
        path = os.path.join(path, part)
        if os.path.islink(path) or not os.path.isdir(path):
            return False
    return os.path.lexists(os.path.join(path, inner.split("/")[-1]))


def _mcp_configs_inside(path, name, deadline=None):
    """Paths, relative to a never-open agent folder, of anything that looks like an MCP server config. Only names
    are read, never contents. Each entry counts once and each folder counts again as a step, against
    0.3.2's MAX_NEVER_OPEN_COUNT; truncated means the walk stopped at that cap or the deadline. Nothing below a
    reported folder is walked. An mcp-named folder of instructions (under skills/, rules/, agents/ …) is not
    reported by name, but a config-shaped file inside it is."""
    path = path.rstrip(os.sep + (os.altsep or "")) or path
    found = [inner for inner in NEVER_OPEN_MCP_PATHS.get(name, ()) if _lexists_inside(path, inner)]
    seen = set(found)
    in_docs = set()
    entries = 0
    truncated = False
    cap = release.MAX_NEVER_OPEN_COUNT

    def stop():
        return entries >= cap or (deadline is not None and entries % release.DEADLINE_TICK == 0 and time.monotonic() > deadline)
    for dirpath, dirs, files in os.walk(path, followlinks=False, onerror=lambda e: None):
        rel = "." if dirpath == path else dirpath[len(path) + 1:].replace(os.sep, "/")
        entries += 1
        if stop():
            truncated = True
            break
        folders = set(dirs)
        under_doc = rel in in_docs
        for f in dirs + files:
            entries += 1
            if stop():
                truncated = True
                break
            inner = f if rel == "." else rel + "/" + f
            parent = name if rel == "." else rel.rsplit("/", 1)[-1]
            folder = f in folders
            if inner in seen:
                continue
            if folder and (under_doc or (NEVER_OPEN_MCP_NAME_RE.search(f) and parent.lower() in MCP_DOC_PARENTS)):
                in_docs.add(inner)  # walked, not named: what decides is a config-shaped file inside
            elif NEVER_OPEN_MCP_NAME_RE.search(f) and not (not folder and MCP_DOC_FILE_RE.search(f)) and not under_doc:
                found.append(inner)
                seen.add(inner)
            elif under_doc and not folder and MCP_CONFIG_FILE_RE.search(f):
                found.append(inner)
                seen.add(inner)
        if truncated:
            break
        dirs[:] = [d for d in dirs if (d if rel == "." else rel + "/" + d) not in seen]  # a reported folder is not walked
    return McpScan(found, truncated)

# ------------------------------------------------------------------ the overlay's walk

def _needs_read(base, ext):
    b = base.lower()
    return ext in release.SQL_LIKE_EXTS or b.endswith(".rules") or b == "database.rules.json" or ext in MODULE_EXTS or b in release.MANIFEST_BASENAMES


def _compressed_could_hold(base, ext):
    """`app.js.zst`, `dump.sql.zst`, `.env.zst`, `key.pem.zst`: a compressed file whose inner name could answer Q1/Q3."""
    inner = base[:-len(ext)]
    inner_ext = os.path.splitext(inner)[1].lower()
    return (release.could_hold_q1_q3(inner, inner_ext) or inner_ext in MODULE_EXTS or release.is_key_file(inner, inner_ext, b"")
            or inner.lower() in release.MANIFEST_BASENAMES)


def overlay_walk(repo, opts, ov, rel_state, caps, clock, end):
    """The overlay's own walk, with 0.3.2's walk rules re-implemented (each from 0.3.2's run_scan): realpath
    containment, linked folders skipped, never-open folders and files walked for names only, EXCLUDED_DIRS plus
    --exclude-dir, hard links and non-regular files skipped, the MAX_DIR_ENTRIES cut, followlinks=False. It
    opens only files it reads (SQL, rules, .mts/.cts, manifests), one at a time. When `caps` is set (0.3.2 hit a
    file or byte cap), files are counted exactly as 0.3.2 counts them and the pass stops where 0.3.2 stopped."""
    real_repo = os.path.realpath(repo)
    candidates = 0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(real_repo, topdown=True, followlinks=False, onerror=lambda e: None):
        if clock() > end:
            ov.stopped_by = "clock"
            raise OverlayTimeout()
        rel_dir = os.path.relpath(dirpath, real_repo).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        parent_name = os.path.basename(dirpath)
        real_dir = os.path.realpath(dirpath)
        if real_dir != real_repo and not real_dir.startswith(real_repo + os.sep):
            dirnames[:] = []
            continue
        if len(dirnames) + len(filenames) > release.MAX_DIR_ENTRIES:
            dirnames[:] = sorted(dirnames, key=release._walk_key)[:release.MAX_DIR_ENTRIES]
            filenames = sorted(filenames)[:max(0, release.MAX_DIR_ENTRIES - len(dirnames))]
        keep = []
        for d in sorted(dirnames, key=release._walk_key):
            full = os.path.join(dirpath, d)
            if d.lower() in release.EXCLUDED_DIRS:
                continue
            try:
                if os.path.islink(full):
                    continue
            except OSError:
                continue
            if release.is_never_open_dir(d, parent_name):
                rel_d = (rel_dir + "/" + d) if rel_dir else d
                scan = _mcp_configs_inside(full, d, end)
                for inner in scan.found:
                    ov.gap(MCP_CHECK, rel_d + "/" + inner)
                if scan.truncated:
                    ov.gap(MCP_CHECK, rel_d, 0, "folder too large to list in full")
                continue
            if d.lower() in opts.excluded:
                continue
            keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            if clock() > end:
                ov.stopped_by = "clock"
                raise OverlayTimeout()
            rel = (rel_dir + "/" + name) if rel_dir else name
            full = os.path.join(dirpath, name)
            ext = os.path.splitext(name)[1].lower()
            module = ext in MODULE_EXTS
            if NEVER_OPEN_SECRET_FILE_RE.match(name):
                ov.gap(MCP_CHECK, rel, 0, "agent config, not opened")
            if release.is_never_open_file(name) or name == ".git":
                continue
            try:
                st = os.lstat(full)
            except OSError:
                if module:
                    ov.gap("code-file-not-read", rel, 0, "could not be read")
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
                if module:
                    ov.gap("code-file-not-read", rel, 0, "a link or special file, not read")
                continue
            lower_rel = rel.lower()
            dirs = lower_rel.split("/")[:-1]
            in_code = "src" in dirs or release.TEST_PATH_RE.search(lower_rel)  # tests/setup.py and src/setup.py are code
            if not in_code and (UNPARSED_MANIFEST_RE.match(name.lower()) or (dirs and dirs[-1] == "requirements" and name.lower().endswith((".txt", ".in")))):
                ov.gap("manifest-not-parsed", rel)
            if ext in COMPRESSED_EXTS and _compressed_could_hold(name, ext):
                ov.gap("compressed-file-not-read", rel, 0, "compressed, not read")
            if release.is_generated(name) or ext in release.PRECOMPRESSED_EXTS:
                continue
            if st.st_size > opts.max_file_bytes:
                if module:
                    ov.gap("code-file-not-read", rel, 0, "larger than the read limit")
                continue
            if ext in release.NEVER_READ_EXTS:
                continue
            if caps:
                if candidates >= opts.max_files or total_bytes + st.st_size > opts.max_total_bytes:
                    ov.stopped_by = "caps"
                    raise OverlayTimeout()  # 0.3.2 stopped here too (its result says so): nothing after this was read
                candidates += 1
                total_bytes += st.st_size
            if not _needs_read(name, ext):
                continue
            opened = release.open_regular(full)
            if opened is None:
                if module:
                    ov.gap("code-file-not-read", rel, 0, "could not be read")
                continue
            fd, size = opened
            try:
                if size > opts.max_file_bytes:
                    continue
                data = release.read_bytes(fd, size)
            finally:
                os.close(fd)
            text = release.decode_text(data) if len(data) == size else None
            if text is None:
                if module:
                    ov.gap("code-file-not-read", rel, 0, "binary or changed while read")
                continue
            sf = OverlayFile(rel, name, ext, text)
            b = name.lower()
            if ext in release.SQL_LIKE_EXTS:
                detect_sql(sf, ov, rel_state)
            if b.endswith(".rules") or b == "database.rules.json":
                detect_rules(sf, ov)
            if module:
                detect_module(sf, ov, opts)
            if b in release.MANIFEST_BASENAMES:
                detect_monitoring(sf, ov)


def overlay_pass(repo, opts, ov, rel_state, result, clock, end):
    caps = bool(result.get("partial")) or result["stats"].get("max_files_hit") or result["stats"].get("max_total_bytes_hit")
    overlay_walk(repo, opts, ov, rel_state, caps, clock, end)
    counter = {}
    for name in sorted(set(ov.tables) - set(rel_state.tables) - rel_state.rls_enabled - ov.rls_enabled):
        if release._cap(counter, "table-without-rls"):
            path, line = ov.tables[name]
            ov.add("table-without-rls", path, line, name, source="sql")
    # text inside a string or comment never turns RLS on: a table 0.3.2 credited from such an enable alone
    for name in sorted(set(rel_state.tables) & rel_state.rls_enabled - ov.rls_enabled):
        if release._cap(counter, "table-without-rls"):
            path, line = rel_state.tables[name]
            ov.add("table-without-rls", path, line, name, source="sql")
    if ov.rule_files == 0 and result["questions"]["q3"]["answer"] == "nothing-found":
        ov.add("no-rule-statements", "", 0, "no SQL file creates a table or policy; no rules file")

# ------------------------------------------------------------------ merge

def _size(result):
    return len(json.dumps(result, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))


def _public(row):
    return {"path": row["path"], "line": row["line"], "snippet": row["snippet"], "check": row["check"]}


def _unfinished_row(status):
    return {"path": "", "line": 0, "snippet": UNFINISHED_SNIPPETS.get(status, UNFINISHED_SNIPPETS["error"]), "check": "checks-not-finished"}


def _confidence(q, answer, evidence):
    if answer == "no":
        return "high"
    if q == "q9":
        return "med" if evidence else "low"
    return "med"


def _evidence_only(row):
    return release.CHECKS.get(row["check"], ("", "evidence"))[1] != "no"


class _Plan(object):
    """One question's merged state: 0.3.2's rows (after the nothing-found row is gone and any displacement), the
    overlay's rows after them, the answer, and whether the overlay changed anything."""
    __slots__ = ("q", "base_answer", "answer", "base_rows", "ov_rows", "unfinished_row", "changed")


def _plans(result, ov):
    plans = {}
    cap = release.MAX_EVIDENCE
    for q in QS:
        qd = result["questions"][q]
        base_rows = list(qd["evidence"])
        taken = set((r["check"], r["path"], r["line"]) for r in base_rows)
        lines = set((r["path"], r["line"]) for r in base_rows if r["line"] > 0)
        rows = []
        for r in ov.rows[q]:
            no = r["_effect"] == "no" and r["_source"] == "mts-key" and q == "q1"  # the clamp: no other overlay row is a No
            if (r["check"], r["path"], r["line"]) in taken or (not no and (r["path"], r["line"]) in lines):
                continue  # 0.3.2 already shows this line on this question
            rows.append(dict(r, _no=no))
        rows.sort(key=lambda r: 0 if r["_no"] else 1)
        want = "no" if any(r["_no"] for r in rows) else ("dont-know" if rows or ov.gaps[q] or not ov.finished else "nothing-found")
        p = _Plan()
        p.q, p.base_answer = q, qd["answer"]
        p.answer = want if RANK[want] > RANK[qd["answer"]] else qd["answer"]
        if p.answer != p.base_answer and p.base_answer == "nothing-found":
            base_rows = [r for r in base_rows if not r["check"].startswith("nothing-found-")]
        if any(r["_no"] for r in rows):  # displacement at insertion: 0.3.2's own ScanState.add rule, Q1 only
            n_no = sum(1 for r in rows if r["_no"])
            while len(base_rows) + n_no > cap:
                for i in range(len(base_rows) - 1, -1, -1):
                    if _evidence_only(base_rows[i]):
                        del base_rows[i]
                        break
                else:
                    break
        room = max(0, cap - len(base_rows))
        p.unfinished_row = None
        if not ov.finished and p.base_answer == "nothing-found":
            p.unfinished_row = _unfinished_row(ov.status)
            room = max(0, room - 1)
        p.base_rows = base_rows
        p.ov_rows = rows[:room]
        p.changed = p.answer != p.base_answer or bool(p.ov_rows) or p.unfinished_row is not None
        plans[q] = p
    return plans


def _assemble(result, plans):
    out = copy.deepcopy(result)
    for q, p in plans.items():
        if not p.changed:
            continue
        evidence = p.base_rows + [_public(r) for r in p.ov_rows] + ([p.unfinished_row] if p.unfinished_row else [])
        qd = out["questions"][q]
        qd["answer"] = p.answer
        qd["evidence"] = evidence
        qd["confidence"] = _confidence(q, p.answer, evidence)
    return out


def _compact(row):
    if row["_no"]:
        return dict(row, snippet="", path=row["path"].rsplit("/", 1)[-1][:40])
    return dict(row, snippet="", path="", line=0)


def _fit(result, plans):
    """Keep the output under 0.3.2's cap without touching a 0.3.2 row of any other question and without ever
    setting partial: drop overlay rows that did not change an answer, then all but one on a question the overlay
    moved (the unfinished row counts as that one), compact what is left, then (Q1 No only) displace 0.3.2's
    evidence-only Q1 rows, compact the No row fully, and as a last step demote it once."""
    cap = release.MAX_OUTPUT_BYTES

    def over():
        return _size(_assemble(result, plans)) > cap

    if not over():
        return _assemble(result, plans)
    moved = lambda p: p.answer != p.base_answer
    # 1. overlay rows on questions whose answer the overlay did not change, the longest list first
    while over():
        idle = [p for p in plans.values() if not moved(p) and p.ov_rows]
        if not idle:
            break
        max(idle, key=lambda p: len(p.ov_rows)).ov_rows.pop()
    # 2. on moved questions, down to one row (the unfinished row is that one when present)
    while over():
        busy = [p for p in plans.values() if moved(p) and len(p.ov_rows) > (0 if p.unfinished_row else 1)]
        if not busy:
            break
        max(busy, key=lambda p: len(p.ov_rows)).ov_rows.pop()
    # 3. compact what is left
    if over():
        for p in plans.values():
            p.ov_rows = [_compact(r) for r in p.ov_rows]
    q1 = plans["q1"]
    no_rows = [r for r in q1.ov_rows if r["_no"]]
    # 4. a Q1 No: displace 0.3.2's evidence-only Q1 rows, last first; then a fully compact No row
    while over() and no_rows:
        for i in range(len(q1.base_rows) - 1, -1, -1):
            if _evidence_only(q1.base_rows[i]):
                del q1.base_rows[i]
                break
        else:
            break
    if over() and no_rows:
        q1.ov_rows = [dict(r, path="", line=0, snippet="") if r["_no"] else r for r in q1.ov_rows]
    # 5. demote the overlay's No, once
    if over() and no_rows:
        base_q1 = result["questions"]["q1"]
        if q1.base_answer == "nothing-found":
            q1.answer = "dont-know"
            q1.ov_rows = [dict(_compact(dict(no_rows[0], _no=False)))]
        else:
            q1.answer = q1.base_answer
            q1.base_rows = list(base_q1["evidence"])
            q1.ov_rows = []
            q1.unfinished_row = None
            q1.changed = False
    if over():
        return None  # the caller falls back to 0.3.2's result with Nothing found withheld
    return _assemble(result, plans)


def fallback(result, status):
    """0.3.2's result with Q1/Q3/Q9 Nothing found withheld: the overlay's answer when it could not run or merge."""
    out = copy.deepcopy(result)
    for q in QS:
        qd = out["questions"][q]
        if qd["answer"] == "nothing-found":
            qd["answer"] = "dont-know"
            qd["evidence"] = [_unfinished_row(status if status in UNFINISHED_SNIPPETS else "error")]
            qd["confidence"] = _confidence(q, "dont-know", qd["evidence"])
    return out


def merge(result, ov):
    """0.3.2's result (deep-copied) and the overlay's findings -> the 0.3.3 result. Answers only move toward
    caution; 0.3.2's rows stay first; partial, stats and every other question are 0.3.2's."""
    for q in QS:
        for r in ov.rows[q]:
            if r["check"] not in OVERLAY_CHECKS and r["check"] not in release.CHECKS:
                raise ValueError("unknown overlay check: " + r["check"])
    if _size(result) > release.MAX_OUTPUT_BYTES:
        return result if ov.finished and not any(ov.rows[q] or ov.gaps[q] for q in QS) else fallback(result, ov.status if not ov.finished else "unfinished")
    out = _fit(result, _plans(result, ov))
    return out if out is not None else fallback(result, ov.status)

# ------------------------------------------------------------------ scan

def overlay_budget_end(started, now, opts):
    """When the overlay must stop: twice 0.3.2's own time, at least OVERLAY_MIN_S (more for a longer
    --deadline-s), and never past OVERLAY_SHARE_OF_DEADLINE of --deadline-s from the start."""
    least = max(OVERLAY_MIN_S, opts.deadline_s / 24.0)
    return min(started + OVERLAY_SHARE_OF_DEADLINE * opts.deadline_s, now + max(least, 2 * (now - started)))


def scan_with_overlay(repo, opts, clock=time.monotonic):
    """(result, 0.3.2's state, overlay status, overlay ms). `clock` must share time.monotonic's base."""
    started = clock()
    state = release.ScanState()
    release.run_scan(repo, state, opts)
    result = copy.deepcopy(release.build_result(state, repo))
    result["version"] = __version__
    if os.environ.get("CUSTODY_CHECK_OVERLAY") == "0":
        return result, state, "skipped", 0
    now = clock()
    end = overlay_budget_end(started, now, opts)
    ov = Overlay(end)
    try:
        if now > end:
            ov.stopped_by = "clock"
            raise OverlayTimeout()
        overlay_pass(repo, opts, ov, state, result, clock, end)
    except (release.Deadline, OverlayTimeout):
        ov.status = "unfinished"
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        ov.status = "error"
    try:
        out = merge(result, ov)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        ov.status = "error"
        out = fallback(result, "error")
    scan_with_overlay.last = ov  # for the tests: how the pass ended and what it found
    return out, state, ov.status, int((clock() - now) * 1000)


def scan(repo, **kwargs):
    if release is None:
        raise ReleaseUnavailable(RELEASE_ERROR)
    opts = release.Options(**kwargs)
    return scan_with_overlay(repo, opts)[0]

# ------------------------------------------------------------------ CLI (0.3.2's main, through the overlay)

def main(argv=None):
    warnings.simplefilter("ignore")  # stderr carries exactly one summary line
    argv = list(sys.argv[1:] if argv is None else argv)
    pretty = "--pretty" in argv
    exit_code = "--exit-code" in argv
    if release is None:
        out = release_envelope(RELEASE_ERROR)
        sys.stdout.write((json.dumps(out, ensure_ascii=True, indent=2) if pretty else json.dumps(out, ensure_ascii=True, separators=(",", ":"))) + "\n")
        sys.stdout.flush()
        return 2 if exit_code else 0
    r = release
    parser = r._Parser(prog="custody_scan.py", add_help=True, description="Read-only evidence gatherer for the eleven custody questions.")
    parser.add_argument("--repo", help="the app folder (run from the folder that contains it)")
    parser.add_argument("--max-files", type=int, default=r.DEFAULT_MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=r.DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=r.DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--deadline-s", type=float, default=r.DEFAULT_DEADLINE_S)
    parser.add_argument("--exclude-dir", action="append", default=[])
    parser.add_argument("--browser-prefix", action="append", default=[])
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--exit-code", action="store_true")
    parser.add_argument("--version", action="store_true")
    started = time.monotonic()
    try:
        args = parser.parse_args(argv)
        if args.version:
            sys.stdout.write(__version__ + "\n")
            return 0
        if not args.repo:
            sys.stderr.write("Missing --repo. Try: python3 custody_scan.py --repo my-app\n")
            raise r.UsageError("--repo is required")
        if args.max_files < 1 or args.max_file_bytes < 1 or args.max_total_bytes < 1 or not args.deadline_s > 0:
            sys.stderr.write("Limits must be positive: --max-files, --max-file-bytes, --max-total-bytes, --deadline-s\n")
            raise r.UsageError("non-positive limit")
        raw_repo = os.path.expanduser(args.repo.rstrip("/") or "/")
        if os.path.islink(raw_repo):
            r.emit(r.envelope("repo-is-symlink"), pretty)
            return 2 if exit_code else 0
        repo = os.path.realpath(raw_repo)
        if not os.path.exists(repo):
            r.emit(r.envelope("repo-not-found"), pretty)
            return 2 if exit_code else 0
        if not os.path.isdir(repo):
            r.emit(r.envelope("repo-not-a-directory"), pretty)
            return 2 if exit_code else 0
        if not os.access(repo, os.R_OK | os.X_OK):
            r.emit(r.envelope("repo-unreadable"), pretty)
            return 2 if exit_code else 0
        try:
            real_cwd = os.path.realpath(os.getcwd())
        except OSError:
            real_cwd = ""
        if real_cwd and real_cwd != repo and real_cwd.startswith(repo + os.sep):
            r.emit(r.envelope("repo-contains-cwd"), pretty)  # `..` from inside the app would walk everything above it
            return 2 if exit_code else 0
        opts = r.Options(max_files=args.max_files, max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes,
                         deadline_s=args.deadline_s, exclude_dirs=args.exclude_dir, browser_prefixes=args.browser_prefix)
        result, state, status, overlay_ms = scan_with_overlay(repo, opts)
        r.emit(result, pretty)
        skipped = sum(state.stats[k] for k in ("files_skipped_oversize", "files_skipped_binary", "files_skipped_generated", "files_never_open", "files_skipped_special"))
        sys.stderr.write("custody-check v%s: scanned %d, skipped %d, errored %d, %d ms; checks 0.3.3: %s, %d ms\n" % (
            __version__, state.files_scanned, skipped, state.stats["files_errored"], int((time.monotonic() - started) * 1000), status, overlay_ms))
        return 3 if (exit_code and result["partial"]) else 0
    except r.UsageError:
        r.emit(r.envelope("usage"), pretty)
        return 2 if exit_code else 0
    except SystemExit:
        raise
    except Exception as exc:  # last resort: never a traceback, never a path
        try:
            r.emit(r.envelope("internal:" + type(exc).__name__), pretty)
        except Exception:
            pass
        return 2 if exit_code else 0


if __name__ == "__main__":
    sys.exit(main())
