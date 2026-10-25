#!/usr/bin/env python3
"""custody_scan.py: read-only evidence gatherer for the eleven custody questions.

Runs on python 3.9+ with the standard library only. Reads a repository (never
its instruction files), never writes, never talks to the network, and prints one
JSON line whose strings have all been through a redaction sweep. Exit code 0
always, unless --exit-code is given.

Run it from the folder that CONTAINS the app:  python3 -I custody_scan.py --repo ./my-app

0.3.3 is 0.3.2 plus an overlay. 0.3.2's scanner (custody_scan_0_3_2.py, a byte-for-byte copy of the release,
checked against RELEASE_SHA256) runs first and alone; the overlay's checks run after it and can only make an
answer more cautious, with one exception (S-044, 0.6.0): a finished overlay drops 0.3.2's `table-without-rls`
evidence rows for tables a DO-block loop turns RLS on for (`_credit_loop_tables`), shows the tables past 0.3.2's
cap of five in their place, and only then lets Q3 reach what 0.3.2 itself would say without those rows:

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

__version__ = "0.6.2"

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

import base64
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

# ------------------------------------------------------------------ the shared rules (S-062), loaded by path

SHARED_EXPORTS = ("STOPLINE_FIELDS", "stopline_terms", "stopline_line_terms", "stopline_kind")


def load_shared():
    """Load shared_rules.py (the stop-line list and matcher custody-check and build-decisions share) from next to
    this file, the way load_release does but with no hash: CI holds every copy byte-equal to the canonical file.
    Returns (module, None) or (None, error code)."""
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

# ------------------------------------------------------------------ overlay constants

OVERLAY_MIN_S = 5.0  # the overlay's least time; a longer --deadline-s raises it (deadline / 24)
OVERLAY_SHARE_OF_DEADLINE = 0.8  # the whole scan ends by this share of --deadline-s, so a host's own timeout never kills it
QS = ("q1", "q3", "q9", "q10")  # Q10 takes evidence rows only (stopline-field); its answer stays 0.3.2's Don't know
RANK = {"nothing-found": 0, "dont-know": 1, "no": 2}
UNFINISHED_SNIPPETS = {"unfinished": "time ran out; rerun with --deadline-s 600",
                       "error": "an error; please report it",
                       "full": "more found than the output can hold"}  # each row shorter than any nothing-found row it replaces

# The one table of overlay checks (S-064, G15): check id -> (the questions its rows go to, effect, the source of a
# No). Overlay rows are evidence except three Q1 Nos: a key in browser-side .mts/.cts code (0.3.2's own check ids,
# source "mts-key"), a browser-prefixed secret NAME read in screen code ("key-name"), and a live named key typed
# into server or unclear code ("key-literal"). The clamp in _plans lets no other source give a No.
NAME_NO_CHECK, NAME_ALSO_CHECK = "browser-secret-env-name", "browser-secret-env-name-also"
FLAG_CHECK, LIVE_KEY_CHECK = "browser-ai-key-flag", "code-key-live-literal"
OVERLAY_TABLE = {
    "mcp-config-not-opened": (("q1",), "evidence", None), "code-file-not-read": (("q1",), "evidence", None),
    "open-rule-unconfirmed": (("q3",), "evidence", None), "open-rule-in-string": (("q3",), "evidence", None),
    "policy-true-unevaluated": (("q3",), "evidence", None), "firebase-rules-test-mode": (("q3",), "evidence", None),
    "firebase-rules-true-unevaluated": (("q3",), "evidence", None), "public-view": (("q3",), "evidence", None),
    "rules-not-read-whole": (("q3",), "evidence", None), "table-dropped": (("q3",), "evidence", None),
    "no-rule-statements": (("q3",), "evidence", None),
    "manifest-not-parsed": (("q9",), "evidence", None),
    "compressed-file-not-read": (("q1", "q3", "q9"), "evidence", None),
    "checks-not-finished": (("q1", "q3", "q9"), "evidence", None),
    "stopline-field": (("q10",), "evidence", None),
    NAME_NO_CHECK: (("q1",), "no", "key-name"),
    NAME_ALSO_CHECK: (("q1",), "evidence", None),
    FLAG_CHECK: (("q1",), "evidence", None),
    LIVE_KEY_CHECK: (("q1",), "no", "key-literal"),
}
OVERLAY_CHECKS = dict((k, qs) for k, (qs, _e, _s) in OVERLAY_TABLE.items())
NO_SOURCES = frozenset(["mts-key"] + [s for _q, e, s in OVERLAY_TABLE.values() if e == "no"])
STOPLINE_CHECK = "stopline-field"
# 0.3.2's schema files (its classify() "schema" kind): the overlay reads these and its SQL files for stop-line fields
SCHEMA_BASENAMES = ("models.py", "schema.rb", "schema.ts", "schema.py", "schema.sql")
CAPPED_PER_SCAN = {"mcp-config-not-opened", "manifest-not-parsed", "compressed-file-not-read", "code-file-not-read"}


def named_per_scan():
    """How many rows of one CAPPED_PER_SCAN check name a file in a whole scan (five); the rest only count as gaps.
    Read from 0.3.2 at call time, like every release constant."""
    return release.MAX_HITS_PER_FILE_PER_CHECK


def all_checks():
    """Every check id the output can hold: 0.3.2's (question, effect) and the overlay's, as {id: (questions, effect)}."""
    out = dict((k, ((q,), e)) for k, (q, e) in release.CHECKS.items())
    out.update((k, (qs, e)) for k, (qs, e, _s) in OVERLAY_TABLE.items())
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
IN_STRING_DETAIL = "named inside a string or function body"  # it may run (`execute '…'`), so it counts; its text is not shown

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
DISABLE_RLS_NAMED_RE = re.compile(r"\balter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?" + _SQL_TABLE + r"\s+disable\s+row\s+level\s+security", re.I)
# S-044: `foreach t in array array['a','b'] loop execute format('alter table %I enable row level security', t); end loop;`
# inside a DO block. Matched on the `code` copy (strings blanked), so a loop inside a string or a function body never counts.
LOOP_HEAD_RE = re.compile(r"\bforeach\s{1,20}([A-Za-z_][A-Za-z0-9_]{0,62})\s{1,20}in\s{1,20}array\s{1,20}array\s{0,20}\[([^\]]{0,4000})\]\s{0,20}loop\b", re.I)
LOOP_END_RE = re.compile(r"\bend\s{1,20}loop\b", re.I)
LOOP_EXECUTE_FORMAT_RE = re.compile(r"\bexecute\s{1,20}format\s{0,20}\(", re.I)  # the format string is blanked in `code`: read it from `text`
LOOP_FORMAT_ARG_RE = re.compile(r"\s{0,20},\s{0,20}([A-Za-z_][A-Za-z0-9_]{0,62})\s{0,20}\)")
LOOP_ENABLE_FORMAT_RE = re.compile(r"\s*alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?(?:public\s*\.\s*)?%I\s+enable\s+row\s+level\s+security\s*;?\s*", re.I)
LOOP_ARRAY_ITEM_RE = re.compile(r"\s*'([a-z_][a-z0-9_]{0,62})'\s*")  # %I keeps case, so only lower-case names fold to the same table
MAX_LOOP_EVENTS = 2000
# Anything that can skip the loop or cut it short voids the credit (review round 1): checked between the DO block's
# `do` and the loop head, and inside the loop body, on the `code` copy so words inside strings never count.
LOOP_DO_RE = re.compile(r"\bdo\b", re.I)
LOOP_CONTROL_RE = re.compile(r"\b(?:if|case|when|exit|continue|return|raise|loop|while|for|exception|goto)\b", re.I)
CREATE_VIEW_RE = re.compile(r"\bcreate\s+(?:or\s+replace\s+)?(?:recursive\s+)?(materialized\s+)?view\s+(?:if\s+not\s+exists\s+)?" + _SQL_TABLE + r"([^;]{0,400})", re.I)
# whichever comes first, as Postgres reads it: a dollar tag may use any letter and has no length limit, and a `$`
# right after a name character is part of that name (`a$b$c`, `x$e'…'` is a name then a plain string). A `$` right
# after a closing tag may open a new tag or an E'…' string; _lex_sql tries SQL_AFTER_TAG_RE there, where the
# lookbehinds would refuse them.
SQL_LEX_OPENER_RE = re.compile(r"--|/\*|\"|(?<![\w$])[Ee]'|'|(?<![\w$])\$(?:[^\W\d]\w*)?\$")
SQL_AFTER_TAG_RE = re.compile(r"\$(?:[^\W\d]\w*)?\$|[Ee]'")
SQL_BLOCK_MARK_RE = re.compile(r"/\*|\*/")  # Postgres block comments nest
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
    """The overlay stopped early: its time ran out between files or inside an agent-folder walk, or it reached the
    file where 0.3.2 hit --max-files or --max-total-bytes. Either way the pass is unfinished."""


# ------------------------------------------------------------------ findings

class Overlay(object):
    """What the overlay found: rows per question (each with its effect and source), gaps, and how the pass ended.
    tick() is the in-file deadline check, on the real monotonic clock like 0.3.2's ScanState.tick."""

    def __init__(self, deadline):
        self.deadline = deadline
        self.ticks = 0
        self.rows = dict((q, []) for q in QS)
        self.gaps = dict((q, 0) for q in QS)
        self.keys = set()
        self.tables = {}  # public table -> (path, line), only tables 0.3.2 did not register
        self.code_tables = set()  # tables whose `create table` the overlay read as code: "a table (name not shown)", not IN_STRING_DETAIL
        self.rls_enabled = set()
        self.rule_files = 0
        self.status = "finished"
        self.stopped_by = None  # "clock" (between files), "tick" (inside a file) or "caps" (where 0.3.2 hit a cap), for the tests
        self.named = {}  # rows per name-only check: five name the files, the gap counts every one
        # S-044 DO-loop RLS credit: events in migration order, resolved after the walk (overlay_pass)
        self.loop_events = []  # (path, offset, table) a loop turns RLS on for
        self.table_events = []  # (kind, path, offset, table or None): create, drop, disable; None = any table
        self.loop_overflow = False
        self.loop_credited = set()
        self.release_open_tables = []  # [(table, path, line)] 0.3.2 would flag, minus credited, in its order and cap
        self.release_q3_clean = False  # 0.3.2's own Nothing found conditions held, apart from its table rows
        self.release_q3_rows = None  # (nothing-found row, summary row) as 0.3.2 writes them
        self.release_q10_terms = {}  # path -> stop-line terms 0.3.2's own Q10 rows name there (S-062)
        self.stopline_found = set()  # every stop-line term found, kept or not: stats.stopline_rows_capped counts the lost ones
        self.stopline_files = []  # (rel, full path, name, ext): schema and SQL files the walk passed, read after it
        self.stopline_unfinished = False  # the stop-line pass ran out of time (fewer rows; the other checks are done)
        # S-064 Q1 key pass (G2): code files the walk passed, read after it; its own finished flag
        self.key_files = []  # (rel, full path, name, ext)
        self.key_finished = True
        self.key_errors = []  # (exception class, sanitized path): a detector that raised; never file text (D2). Tests read it; the report does not
        self.key_cands = []  # name references, judged after the pass (R2)
        self.pkg_next = {}  # package folder -> its package.json lists next (unread or unparsed: True) (G4)
        self.next_config_dirs = set()  # folders holding a next.config.*
        self.q1_no_lines = set()  # (path, line) that already hold a Q1 No: 0.3.2's or an .mts one (G7, G14)

    def stopline(self, path, line, term):
        """A Q10 stop-line row. Its snippet is the list term, never the app's identifier."""
        self.stopline_found.add(term)
        self.add(STOPLINE_CHECK, path, line, term, source="schema")

    def table_event(self, kind, path, offset, name):
        if len(self.table_events) >= MAX_LOOP_EVENTS:
            self.loop_overflow = True
            return
        self.table_events.append((kind, path, offset, name))

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
            kept = self.rows[q]
            if len(kept) < 2 * release.MAX_EVIDENCE:
                kept.append(dict(row, _effect=effect, _source=source))
            elif effect == "no":  # 0.3.2's own add() rule: a No is never crowded out, it takes the last caution's place
                for i in range(len(kept) - 1, -1, -1):
                    if kept[i]["_effect"] != "no":
                        old = kept[i]
                        self.keys.discard((q, old["check"], old["path"], old["line"], old["snippet"]))
                        kept[i] = dict(row, _effect=effect, _source=source)
                        break
                else:
                    continue
            else:
                continue  # only kept rows are remembered, so memory stays bounded however many matches a file has
            self.keys.add(key)

    def gap(self, check, path, line=0, snippet="", questions=None):
        """A thing the overlay could not look at: a named row, so no gap shows as a bare summary row. Name-only
        checks (an agent folder's configs, unparsed manifests) name five files per scan; the gap counts all."""
        if check in CAPPED_PER_SCAN:
            self.named[check] = self.named.get(check, 0) + 1
            if self.named[check] > named_per_scan():
                for q in (questions or OVERLAY_CHECKS[check]):
                    self.gaps[q] += 1
                return
        self.add(check, path, line, snippet, gap=True, questions=questions)


class OverlayFile(object):
    __slots__ = ("rel", "base", "ext", "text")

    def __init__(self, rel, base, ext, text):
        self.rel, self.base, self.ext, self.text = rel, base, ext, text


# A row the overlay builds from a SQL or rules file shows one of these, never the file's own text, so a lexer
# that misreads a string can never print what it holds; path:line points at the rule.
SNIPPET_LABELS = {
    "rls-disabled": "disable row level security",
    "using-true": "using (true)",
    "policy-with-check-true": "with check (true)",
    "policy-to-anon": "a policy for anon",
    "storage-bucket-public-sql": "a storage bucket set public",
    "cron-schedule": "cron.schedule (job not shown)",
    "firebase-if": "allow \u2026: if \u2026 (condition not shown)",
    "firebase-test-mode": "allow \u2026: if request.time < \u2026 (test mode)",
    "rtdb-test-mode": '"now < \u2026" (test mode)',
    "rtdb-write-true": '".write": true',
    "rtdb-read-true": '".read": true',
    "rule-in-string": "rule text inside a string or function body (not shown)",
}
# Names the overlay found by itself are not shown either: a name is only text the file chose, and reading it right
# needs the file read exactly as Postgres would. 0.3.2's own rows keep their names.
NAME_LABELS = {"table": "a table (name not shown)", "view": "a view (name not shown)"}


def _name(kind, in_code):
    return NAME_LABELS[kind] if in_code else IN_STRING_DETAIL


def _finditer_rows(regex, text, sf, ov, check, counter):
    """`text` is the file with strings blanked (`code`): a match inside a string is 0.3.2's to judge."""
    for m in regex.finditer(text):
        ov.tick()
        if not release._cap(counter, check):
            break
        ov.add(check, sf.rel, release.line_of(text, m.start()), SNIPPET_LABELS[check], source="sql")

# ------------------------------------------------------------------ SQL

def _blank(chunk):
    return NOT_NEWLINE_RE.sub(" ", chunk) if "\n" in chunk else " " * len(chunk)


def _block_comment_end(text, start, tick=None):
    """The offset just past the */ that closes a /* opened before `start`, counting nested /* */ pairs as Postgres
    does, or -1 when the nest never closes. Each marker is read once."""
    depth = 1
    for t in SQL_BLOCK_MARK_RE.finditer(text, start):
        if tick is not None:
            tick()
        depth += 1 if t.group(0) == "/*" else -1
        if depth == 0:
            return t.end()
    return -1


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

    after_tag = -1  # where the last dollar quote closed
    nest_failed = False  # a nested comment never closed: comments close at the first */ from then on

    while pos < n:
        if tick is not None:
            tick()
        m = SQL_AFTER_TAG_RE.match(text, pos) if pos == after_tag else None
        m = m or SQL_LEX_OPENER_RE.search(text, pos)
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
            if no_block_close:
                k = -1
            elif nest_failed:
                k = text.find("*/", m.end())
                k = k + 2 if k >= 0 else -1
            else:
                k = _block_comment_end(text, m.end(), tick)
                if k < 0:  # Postgres would read the rest as one comment; read it as 0.3.2 does (MySQL, SQLite too):
                    nest_failed = True  # the first */ closes, here and for every later comment, keeping one pass
                    k = text.find("*/", m.end())
                    k = k + 2 if k >= 0 else -1
            if k < 0:
                no_block_close = True  # no */ anywhere after this: later openers skip the search, keeping one pass
                emit(tok, tok, tok)
                pos = m.end()
                continue
            stop = k
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
                stop = after_tag = close + len(tok)
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


def _paren_closes(text, tick=None):
    """Each '(' offset mapped to the offset of the ')' that brings the level back down: one pass, linear."""
    closes, stack = {}, []
    for m in PAREN_RE.finditer(text):
        if tick is not None:
            tick()
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


def _loop_credits(sf, ov, text, code):
    """S-044: record each table a DO-block loop turns RLS on for (see LOOP_HEAD_RE). Only the exact shape counts:
    array literals of plain lower-case names, and `execute format('alter table [public.]%I enable row level
    security', <the loop variable>)` inside the loop. Credit is decided later, in migration order."""
    heads = list(LOOP_HEAD_RE.finditer(code))
    if not heads:
        return
    dos = [d.start() for d in LOOP_DO_RE.finditer(code)]
    ends = [(e.start(), e.end()) for e in LOOP_END_RE.finditer(code)]  # found once per file, then bisected
    for m in heads:
        ov.tick()
        var = m.group(1).lower()
        names = []
        for item in text[m.start(2):m.end(2)].split(","):
            t = LOOP_ARRAY_ITEM_RE.fullmatch(item)
            if t:
                names.append(t.group(1))
        i = bisect.bisect_left(ends, (m.end(), 0))
        d = bisect.bisect_left(dos, m.start()) - 1
        if not names or i == len(ends) or d < 0:
            continue
        end_start = ends[i][0]
        if LOOP_CONTROL_RE.search(code, dos[d] + 2, m.start()) or LOOP_CONTROL_RE.search(code, m.end(), end_start):
            continue  # the loop might not run, or might stop before every name
        enables = False
        for e in LOOP_EXECUTE_FORMAT_RE.finditer(code, m.end(), end_start):
            ov.tick()
            start = re.compile(r"\s{0,20}").match(text, e.end()).end()
            if text[start:start + 1] != "'":
                continue  # a plain '…' string only: no E'…', no $tag$, no variable
            body = SQL_PLAIN_BODY_RE.match(text, start + 1)
            if not body or body.end() > end_start:
                continue
            fmt = text[start + 1:body.end() - 1].replace("''", "'")
            arg = LOOP_FORMAT_ARG_RE.match(code, body.end())
            if arg and arg.group(1).lower() == var and LOOP_ENABLE_FORMAT_RE.fullmatch(fmt):
                enables = True
        if not enables:
            continue
        for name in names:
            if len(ov.loop_events) >= MAX_LOOP_EVENTS:
                ov.loop_overflow = True
                return
            ov.loop_events.append((sf.rel, m.start(), name))


def _resolve_loop_credits(ov):
    """A loop's credit holds unless the same table (or any table, for an unnamed statement) is disabled or dropped
    anywhere else or later in the same file, or created again later in migration order (files by name)."""
    if ov.loop_overflow:
        return set()
    credited = set()
    for path, offset, name in ov.loop_events:
        here = (path, offset)
        ok = True
        for kind, epath, eoffset, ename in ov.table_events:
            if ename is not None and ename != name:
                continue
            if kind == "create":
                ok = (epath, eoffset) < here
            else:
                ok = epath == path and eoffset < offset
            if not ok:
                break
        if ok:
            credited.add(name)
    return credited


def detect_sql(sf, ov, rel_state):
    counter = {}
    text, code, bare, unclosed = _lex_sql(sf.text, tick=ov.tick)
    if RULE_SQL_RE.search(code):
        ov.rule_files += 1
    if unclosed:
        ov.gap("rules-not-read-whole", sf.rel, 0, "a quote or $tag$ that never closes")
    low = bare.translate(ASCII_LOWER)
    closes, budget = None, {"left": len(text) + MAX_PREDICATE_CHARS}
    named_disables = dict((m.end(), release._public_table(m.group(1))) for m in DISABLE_RLS_NAMED_RE.finditer(text))
    for m in RLS_DISABLED_RE.finditer(text):
        ov.tick()
        ov.table_event("disable", sf.rel, m.start(), named_disables.get(m.end()))  # unnamed (`%I`, a string) = any table
        check = "open-rule-unconfirmed" if _in_code(m, bare) else "open-rule-in-string"
        if release._cap(counter, check):
            ov.add(check, sf.rel, release.line_of(text, m.start()), SNIPPET_LABELS["rls-disabled" if check != "open-rule-in-string" else "rule-in-string"], source="sql")
    for m in USING_TRUE_RE.finditer(text):
        ov.tick()
        in_code = _in_code(m, bare)
        check = _policy_kind(low, max(0, m.start() - 2000), m.start())
        rec = {}
        if in_code and not release.USING_TRUE_RE.match(text, m.start()):  # a string's predicate is never read: its row says so
            if closes is None:
                closes = _paren_closes(bare, ov.tick)  # only when a group needs reading; parens in strings do not count
            if time.monotonic() > ov.deadline:  # one predicate can cost thousands of ticks' work: check the clock before each
                ov.stopped_by = "tick"
                raise release.Deadline()
            if not _sql_predicate_open(bare, m.start(), closes, budget, rec):
                check = "policy-true-unevaluated"
        check = _caution(check) if in_code else "open-rule-in-string"
        if release._cap(counter, check):
            nested = check == "policy-true-unevaluated" and rec.get("exhausted")
            ov.add(check, sf.rel, release.line_of(text, m.start()), NESTED_DETAIL % rec["chars"] if nested else SNIPPET_LABELS["using-true" if check != "open-rule-in-string" else "rule-in-string"], source="sql")
    _finditer_rows(WITH_CHECK_TRUE_RE, code, sf, ov, "policy-with-check-true", counter)
    _finditer_rows(release.POLICY_TO_ANON_RE, code, sf, ov, "policy-to-anon", counter)
    _finditer_rows(release.STORAGE_BUCKET_TRUE_RE, code, sf, ov, "storage-bucket-public-sql", counter)
    _finditer_rows(release.CRON_SQL_RE, code, sf, ov, "cron-schedule", counter)
    pos, line = 0, 1
    for n, m in enumerate(CREATE_TABLE_RE.finditer(text)):
        if n >= release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, 0, "more create table statements than the scanner reads")
            break
        ov.tick()
        line += text.count("\n", pos, m.start())
        pos = m.start()
        name = release._public_table(m.group(1))
        if name:
            ov.table_event("create", sf.rel, m.start(), name)
        if name and code[m.start():m.end()] == m.group(0) and len(ov.code_tables) < release.MAX_SEEN:
            ov.code_tables.add(name)
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
    pos, line = 0, 1
    for n, m in enumerate(DROP_TABLE_RE.finditer(text)):
        if n >= release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, 0, "more drop table statements than the scanner reads")
            break
        ov.tick()
        line += text.count("\n", pos, m.start())  # counted forward once per statement, never from the top per name
        pos = m.start()
        parts = m.group(1).split(",")
        in_code = code[m.start():m.end()] == m.group(0)  # a list that reaches into a string or body: IN_STRING_DETAIL
        if len(m.group(1)) >= MAX_DROP_LIST_CHARS or len(parts) > release.MAX_TABLE_MATCHES_PER_FILE:
            ov.gap("rules-not-read-whole", sf.rel, line, "a drop list too long to read whole")
        for part in parts[:release.MAX_TABLE_MATCHES_PER_FILE]:
            ov.tick()
            t = DROP_ITEM_RE.match(part)
            name = release._public_table(t.group(1)) if t else None
            ov.table_event("drop", sf.rel, m.start(), name)  # a list it cannot name drops "any table"
            # a table dropped and made again loses its RLS; unless this file turns it back on afterwards, migration
            # order across files decides, and the scanner does not replay migrations
            if name and enabled_at.get(name, -1) < m.start():
                if release._cap(counter, "table-dropped"):
                    ov.gap("table-dropped", sf.rel, line, _name("table", in_code))
                else:
                    for q in OVERLAY_CHECKS["table-dropped"]:
                        ov.gaps[q] += 1  # named five times per file; every one still keeps Q3 off Nothing found
    _loop_credits(sf, ov, text, code)
    counter_views = {}
    for m in CREATE_VIEW_RE.finditer(text):
        ov.tick()
        name = release._public_table(m.group(2))
        # a view runs as its owner and skips the table's RLS unless security_invoker is set; a materialized view has no RLS at all
        head = VIEW_AS_RE.split(m.group(3), 1)[0]
        options = " ".join(w.group(1) + ")" for w in VIEW_WITH_RE.finditer(head))
        if name and (m.group(1) or not SAFE_INVOKER_RE.search(options)) and release._cap(counter_views, "public-view"):
            in_code = code[m.start():m.end(2)] == text[m.start():m.end(2)]
            ov.add("public-view", sf.rel, release.line_of(text, m.start()), _name("view", in_code), source="sql")

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


def _firebase_ifs(text, tick=None):
    """([(rule head match, end of its condition)] for conditions of at most MAX_FIREBASE_CONDITION characters,
    count of longer ones); the condition is text[head.end():end]: a condition runs from the
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
            found.append((head, e))
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
    for head, end in ifs:
        ov.tick()
        rec = {}
        cond = text[head.end():end]
        verdict = _firebase_condition(cond, rec)
        if verdict == "open" and sf.text[head.end():end] != cond:
            verdict = "unevaluated"  # a `/*` or `//` inside the condition (often inside a string) was cut as a comment
        if verdict == "open":
            check = "open-rule-unconfirmed" if release.FIREBASE_WRITE_RE.search(head.group(1)) else "firebase-rules-public-read"
        elif verdict == "unevaluated":
            check = "firebase-rules-true-unevaluated"
        else:
            continue
        if release._cap(counter, check):
            nested = verdict == "unevaluated" and rec.get("exhausted")
            ov.add(check, sf.rel, release.line_of(text, head.start()), NESTED_DETAIL % rec["chars"] if nested else SNIPPET_LABELS["firebase-if"], source="rules")
    for _ in range(long_n):
        ov.tick()
        ov.gap("rules-not-read-whole", sf.rel, 0, "a condition longer than the scanner reads")
    for regex, label in ((FIREBASE_TEST_MODE_RE, "firebase-test-mode"), (RTDB_TEST_MODE_RE, "rtdb-test-mode")):
        for m in regex.finditer(text):
            ov.tick()
            if release._cap(counter, "firebase-rules-test-mode"):
                ov.add("firebase-rules-test-mode", sf.rel, release.line_of(text, m.start()), SNIPPET_LABELS[label], source="rules")
    for m in RTDB_WRITE_OPEN_RE.finditer(text):
        ov.tick()
        if release._cap(counter, "open-rule-unconfirmed"):
            ov.add("open-rule-unconfirmed", sf.rel, release.line_of(text, m.start()), SNIPPET_LABELS["rtdb-write-true"], source="rules")
    for m in RTDB_READ_OPEN_RE.finditer(text):
        ov.tick()
        if release._cap(counter, "firebase-rules-public-read"):
            ov.add("firebase-rules-public-read", sf.rel, release.line_of(text, m.start()), SNIPPET_LABELS["rtdb-read-true"], source="rules")

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
        if lname in MONITORING_DEPS or stripped in MONITORING_DEPS:
            shown = lname if lname in MONITORING_DEPS else stripped  # the scanner's own list entry
        elif lname.startswith(MONITORING_PREFIXES):
            shown = [f for f in MONITORING_PREFIXES if lname.startswith(f)][0] + "\u2026 (name not shown)"  # the rest is the file's text
        else:
            continue
        if release._cap(counter, "monitoring-dependency"):
            ov.add("monitoring-dependency", sf.rel, 0, shown, source="manifest")

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
    0.3.2's MAX_NEVER_OPEN_COUNT; truncated means the walk stopped at that cap. Past the deadline it raises
    OverlayTimeout, so the pass ends unfinished instead of calling a clock stop a size cap. Nothing below a
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
        if deadline is not None and entries % release.DEADLINE_TICK == 0 and time.monotonic() > deadline:
            raise OverlayTimeout()
        return entries >= cap
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


def _stopline_file(base, ext):
    return ext in release.SQL_LIKE_EXTS or ext in release.SCHEMA_EXTS or base.lower() in SCHEMA_BASENAMES


def detect_stopline(sf, ov, past_end=lambda: False):
    """S-062: a Q10 row per stop-line term in a schema or SQL file (the shared matcher: comments and string values
    never count), unless 0.3.2's own Q10 rows already name that term on this path. One row per term per file, at
    its first line. Raises release.Deadline when past_end() says the pass's time is up."""
    named = ov.release_q10_terms.get(release.sanitize_path(sf.rel), ())
    seen = set()
    for k, (line_no, _identifier, term) in enumerate(shared.stopline_line_terms(sf.text, shared.stopline_kind(sf.base))):
        if k % release.DEADLINE_TICK == 0 and past_end():
            raise release.Deadline()
        if term in named or term in seen:
            continue
        seen.add(term)
        ov.stopline(sf.rel, line_no, term)


def _read_text(full, opts):
    """(text, why): a regular file's text, or None and why it was not read ("" for one over the size limit, which
    0.3.2 counts itself)."""
    opened = release.open_regular(full)
    if opened is None:
        return None, "could not be read"
    fd, size = opened
    try:
        if size > opts.max_file_bytes:
            return None, ""
        data = release.read_bytes(fd, size)
    finally:
        os.close(fd)
    text = release.decode_text(data) if len(data) == size else None
    return text, "" if text is not None else "binary or changed while read"


def stopline_pass(ov, opts, clock=time.monotonic, end=float("inf")):
    """After the walk and the other overlay checks (the key pass runs after this one): the stop-line fields of the files the walk passed, in the time left.
    Running out stops only this pass. A file not read here means fewer stop-line rows, which main never had."""
    past_end = lambda: clock() > end  # noqa: E731
    try:
        for rel, full, name, ext in ov.stopline_files:
            if past_end():
                raise release.Deadline()
            text, _why = _read_text(full, opts)
            if text is not None:
                detect_stopline(OverlayFile(rel, name, ext, text), ov, past_end)
    except release.Deadline:
        ov.stopline_unfinished = True


# ------------------------------------------------------------------ S-064: the Q1 key pass (custody 0.6.2)
# Gap 1: a browser-prefixed secret NAME read in screen code ships its value to every visitor, even when .env is not
# in the clone. Gap 2: a live named key typed into server or unclear code is a key to replace, so 0.3.2's evidence
# row for it becomes a No. Plan Steps 2-3 (~/.claude/plans/idempotent-wishing-feigenbaum.md).

NEXT_CONFIG_RE = re.compile(r"^next\.config\.(?:js|mjs|ts|cjs)$")
_ENV_NAME = r"[A-Za-z_][A-Za-z0-9_]{0,127}"
ENV_ACCESS_RE = re.compile(r"(?<![\w$.])(import\.meta\.env|process\.env)\s{0,5}(?:\??\.\s{0,5}(" + _ENV_NAME + r")|(?:\?\.)?\s{0,5}\[\s{0,5}([\"'`])(" + _ENV_NAME + r")\3\s{0,5}\])")
ENV_DESTRUCTURE_RE = re.compile(r"\{([^{}]{0,2000})\}\s{0,20}=\s{0,20}(import\.meta\.env|process\.env)\b")
DESTRUCTURE_KEY_RE = re.compile(r"(?:^|[{,])\s{0,200}(" + _ENV_NAME + r")\s{0,200}(?=[:,=]|$)")
AI_FLAG_RE = re.compile(r"\bdangerouslyAllowBrowser\s{0,5}:\s{0,5}true\b")
PROVIDER_KEY_RE = re.compile(r"^(?:" + release.MODEL_PROVIDER_ALT + r")_[A-Z0-9_]*(?:KEY|TOKEN|SECRET)$", re.I) if release else None
SECRET_SUFFIX_RE = re.compile(r"(?:_KEY|_TOKEN|_SECRET|_SERVICE_ROLE|_ROLE_KEY)$|^SECRET$", re.I)
INLINED_PROCESS_PREFIXES = ("NEXT_PUBLIC_", "REACT_APP_", "EXPO_PUBLIC_")  # bundlers inline these from process.env
JS_COMMENT_RE = re.compile(r"//[^\n]*|/\*(?:[^*]|\*(?!/))*(?:\*/|$)|\"(?:[^\"\\\n]|\\.)*\"?|'(?:[^'\\\n]|\\.)*'?|`(?:[^`\\]|\\.)*`?")  # an unclosed quote ends at its line, so the scan stays linear
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro"}
MAX_NAME_SNIPPET = 64
PROMOTED_CHECKS = ("server-path-key-literal", "non-client-key-literal")


def _dir_of(rel):
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def _lists_next(text):
    """True when a package.json lists next in dependencies or devDependencies, or cannot be read as one (G4)."""
    try:
        pj = json.loads(text)
    except (ValueError, RecursionError):
        return True
    if not isinstance(pj, dict):
        return True
    for k in ("dependencies", "devDependencies"):
        deps = pj.get(k)
        if isinstance(deps, dict) and "next" in deps:
            return True
    return False


def _is_next(rel, ov):
    """The nearest package root above the file is a Next app (G4); the repo root when there is none."""
    d = _dir_of(rel)
    while True:
        if d in ov.next_config_dirs:
            return True
        if d in ov.pkg_next:
            return ov.pkg_next[d]
        if not d:
            return False
        d = _dir_of(d)


def secret_name_prefix(name, opts):
    """The browser prefix of NAME when the rest of it names a secret (S2, C3), else None."""
    up = name.upper()
    for p in opts.prefixes:
        if up.startswith(p.upper()):
            rest = name[len(p):]
            if rest and ((release.IDENT_SENSITIVE_RE.search(rest) and SECRET_SUFFIX_RE.search(rest))
                         or PROVIDER_KEY_RE.match(rest)):
                return p
            return None
    return None


def _comment_spans(text, ov):
    """(start, end) of each // and /* */ comment in JS-like code; strings are skipped so `'//'` is not one."""
    spans = []
    for k, m in enumerate(JS_COMMENT_RE.finditer(text)):
        if k % release.DEADLINE_TICK == 0:
            ov.tick()
        if m.group(0)[:1] == "/":
            spans.append((m.start(), m.end()))
    return spans


def _jwt_iss(token):
    try:
        part = token.split(".")[1]
        if len(part) > 4096:
            return None
        data = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)).decode("utf-8"))
        return data.get("iss") if isinstance(data, dict) else None
    except Exception:
        return None


def _live_on_line(line_text):
    """A live named key (not test mode, not a placeholder) or a service_role JWT that is not Supabase's demo key."""
    for m in release.NAMED_KEY_RE.finditer(line_text):
        v = m.group(0)
        if not release.TEST_MODE_KEY_RE.match(v) and not release.is_placeholder(v, False):
            return True
    for s, e in release.find_jwts(line_text):
        tok = line_text[s:e]
        if release.decode_jwt_role(tok) == "service_role" and _jwt_iss(tok) != "supabase-demo" and not release.is_placeholder(tok, True):
            return True
    return False


def detect_keys(sf, ov, opts):
    """One code file: name references (judged after the pass), the AI SDK browser flag (evidence), and live keys
    0.3.2 left as evidence in server or unclear code (promoted to a No). An .mts/.cts file reads as its .ts sibling."""
    module = sf.ext in MODULE_EXTS
    rel_ts, base_ts, ext_ts = (_ts_name(sf.rel), _ts_name(sf.base), ".ts") if module else (sf.rel, sf.base, sf.ext)
    text = sf.text
    cls, kinds = release.classify(rel_ts, base_ts, ext_ts, text)
    path = release.sanitize_path(sf.rel)
    test = bool(release.TEST_PATH_RE.search(sf.rel))
    spans = starts = None

    def in_comment(pos):
        nonlocal spans, starts
        if sf.ext not in JS_EXTS:
            return False
        if spans is None:
            spans = _comment_spans(text, ov)
            starts = [s for s, _ in spans]
        i = bisect.bisect_right(starts, pos) - 1
        return i >= 0 and spans[i][1] > pos

    if cls != "server" and ("import.meta.env" in text or "process.env" in text):
        refs = []
        for m in ENV_ACCESS_RE.finditer(text):
            ov.tick()
            refs.append((m.group(2) or m.group(4), m.group(1), m.start()))
        for m in ENV_DESTRUCTURE_RE.finditer(text):
            ov.tick()
            for k in DESTRUCTURE_KEY_RE.finditer(m.group(1)):
                refs.append((k.group(1), m.group(2), m.start()))
        nxt = None
        for name, acc, pos in refs:
            prefix = secret_name_prefix(name, opts)
            if prefix is None or len(ov.key_cands) >= release.MAX_SEEN:
                continue
            if nxt is None:
                nxt = _is_next(sf.rel, ov)
            ov.key_cands.append({"name": name, "acc": acc, "prefix": prefix, "rel": sf.rel, "path": path,
                                 "line": release.line_of(text, pos), "cls": cls, "comment": in_comment(pos), "test": test, "next": nxt})
    if cls != "server" and not test and "dangerouslyAllowBrowser" in text:
        n = 0
        for m in AI_FLAG_RE.finditer(text):
            ov.tick()
            if in_comment(m.start()):
                continue
            n += 1
            if n > release.MAX_HITS_PER_FILE_PER_CHECK:
                break
            ov.add(FLAG_CHECK, sf.rel, release.line_of(text, m.start()), "dangerouslyAllowBrowser: true", source="key-flag")
    rsf = release.ScanFile(rel_ts, base_ts, ext_ts, cls, kinds, text)
    if cls in ("server", "other") and release._q1_gate(rsf, opts):
        scratch = release.ScanState()
        scratch.deadline = ov.deadline
        claimed = []
        release.detect_browser_prefix(rsf, scratch, opts, claimed)
        release.detect_key_literals(rsf, scratch, opts, claimed)
        lines = None
        ts_path = release.sanitize_path(rel_ts)
        for row in scratch.evidence["q1"]:
            if row["check"] not in PROMOTED_CHECKS:
                continue
            ov.tick()
            if lines is None:
                lines = text.split("\n")
            n = row["line"]
            if not (0 < n <= len(lines)) or not _live_on_line(lines[n - 1]):
                continue
            rpath = path if row["path"] == ts_path else row["path"]
            if (rpath, n) in ov.q1_no_lines:
                continue
            ov.add(LIVE_KEY_CHECK, sf.rel if row["path"] == ts_path else row["path"], n, row["snippet"], effect="no", source="key-literal")


def _judge_names(ov, opts, rel_state):
    """After the pass (R2): each name reference becomes no row (server), `-also` evidence (comment, test path, a
    process.env name a bundler does not inline in an unclear file, an unclear file in a Next app), or a No candidate.
    Per NAME the first No candidate in sorted (path, line) is the No, unless 0.3.2 already gave that NAME a No (F3)."""
    prefix_alt = "|".join(re.escape(p) for p in opts.prefixes)
    name_re = re.compile(r"\b(?:" + prefix_alt + r")[A-Za-z0-9_]+")
    judged = set()
    for row in rel_state.evidence["q1"]:
        if row["check"].startswith("browser-prefix-") and release.CHECKS[row["check"]][1] == "no":
            judged.update(n.upper() for n in name_re.findall(row["snippet"]))
    candidates = {}
    also = []
    for c in ov.key_cands:
        if c["cls"] == "server":
            continue
        unclear = c["cls"] == "other"
        if c["comment"] or c["test"] or (unclear and c["next"]) or \
                (unclear and c["acc"] == "process.env" and c["prefix"].upper() not in INLINED_PROCESS_PREFIXES):
            also.append(c)
        else:
            candidates.setdefault(c["name"].upper(), []).append(c)
    nos = []
    for name in sorted(candidates):
        group = sorted(candidates[name], key=lambda c: (c["path"], c["line"]))
        first = None if name in judged else group[0]
        for c in group:
            (nos if c is first else also).append(c)
    for c in nos:
        if (c["path"], c["line"]) not in ov.q1_no_lines:
            ov.add(NAME_NO_CHECK, c["rel"], c["line"], c["name"][:MAX_NAME_SNIPPET], effect="no", source="key-name")
    shown = {}
    for c in sorted(also, key=lambda c: (c["path"], c["line"])):
        shown[c["path"]] = shown.get(c["path"], 0) + 1
        if shown[c["path"]] <= release.MAX_HITS_PER_FILE_PER_CHECK:
            ov.add(NAME_ALSO_CHECK, c["rel"], c["line"], c["name"][:MAX_NAME_SNIPPET], source="key-name-also")


def _key_gap(ov, rel, why, named):
    if release.sanitize_path(rel) not in named:  # 0.3.2 already shows this file on Q1 (G14)
        ov.gap("code-file-not-read", rel, 0, why)


def key_pass(ov, opts, rel_state, clock=time.monotonic, end=float("inf")):
    """S-064 (G2): after the walk and the stop-line pass, the code files the walk passed, in the time left. Running
    out leaves only Q1 unfinished (Don't know, never Nothing found); the rows found so far stand. A detector error on
    one file is a Q1 gap for that file and the rest of the pass goes on (D2, G1)."""
    past_end = lambda: clock() > end  # noqa: E731
    named = set(r["path"] for r in rel_state.evidence["q1"])
    ov.q1_no_lines = set((r["path"], r["line"]) for r in rel_state.evidence["q1"] if release.CHECKS[r["check"]][1] == "no")
    ov.q1_no_lines.update((r["path"], r["line"]) for r in ov.rows["q1"] if r["_effect"] == "no" and r["_source"] == "mts-key")
    stopped_by = ov.stopped_by
    try:
        for rel, full, name, ext in ov.key_files:
            if past_end():
                raise release.Deadline()
            text, why = _read_text(full, opts)
            if text is None:
                if why:
                    _key_gap(ov, rel, why, named)
                continue
            if not ("import.meta.env" in text or "process.env" in text or "dangerouslyAllowBrowser" in text or opts.prefilter_re.search(text)):
                continue
            try:
                detect_keys(OverlayFile(rel, name, ext, text), ov, opts)
            except (release.Deadline, OverlayTimeout):
                raise
            except Exception as exc:
                ov.key_errors.append((type(exc).__name__, release.sanitize_path(rel)))
                _key_gap(ov, rel, "the key check stopped on an error", named)
    except (release.Deadline, OverlayTimeout):
        ov.key_finished = False
        ov.stopped_by = stopped_by  # the walk's own ending is unchanged
    _judge_names(ov, opts, rel_state)


def note_release_q10(ov, result):
    """The stop-line terms 0.3.2's own Q10 rows name: the overlay does not repeat them on that path, and a later trim
    that drops one is counted in stats.stopline_rows_capped like an overlay row."""
    for r in result["questions"]["q10"]["evidence"]:
        terms = shared.stopline_terms(r["snippet"])
        ov.release_q10_terms.setdefault(r["path"], set()).update(terms)
        ov.stopline_found.update(terms)


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
                try:
                    scan = _mcp_configs_inside(full, d, end)
                except OverlayTimeout:
                    ov.stopped_by = "clock"
                    raise
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
            if NEVER_OPEN_SECRET_FILE_RE.match(name):  # 0.3.2 never opens opencode.json or .aider*; it reads opencode.jsonc as text
                ov.gap(MCP_CHECK, rel, 0, "agent config, not opened" if release.is_never_open_file(name) else "agent config; MCP servers not checked")
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
            if name == "package.json":
                ov.pkg_next[_dir_of(rel)] = True  # Next until it is read and says otherwise (G4: fewer Nos)
            elif NEXT_CONFIG_RE.match(name):
                ov.next_config_dirs.add(_dir_of(rel))
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
            if _stopline_file(name, ext):
                ov.stopline_files.append((rel, full, name, ext))  # read after the walk (stopline_pass)
            if ext in release.CODE_EXTS or module:
                ov.key_files.append((rel, full, name, ext))  # read after the walk (key_pass)
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
            if name == "package.json":
                ov.pkg_next[_dir_of(rel)] = _lists_next(text)


def overlay_pass(repo, opts, ov, rel_state, result, clock, end):
    caps = bool(result.get("partial")) or result["stats"].get("max_files_hit") or result["stats"].get("max_total_bytes_hit")
    note_release_q10(ov, result)
    overlay_walk(repo, opts, ov, rel_state, caps, clock, end)
    # a capped or partial scan may have missed a later migration that turns RLS off: no credit (review round 1)
    ov.loop_credited = set() if caps else _resolve_loop_credits(ov) & (set(ov.tables) | set(rel_state.tables))
    open_release = sorted(set(rel_state.tables) - rel_state.rls_enabled - ov.loop_credited)
    ov.release_open_tables = [(n,) + tuple(rel_state.tables[n]) for n in open_release[:release.MAX_TABLE_WITHOUT_RLS_ROWS]]
    ov.release_q3_clean = not caps and bool(rel_state.rule_files) and not rel_state.gaps["q3"]
    ov.release_q3_rows = (
        release._row("nothing-found-rules", "%s read: no RLS disabled, no using (true) policy, no if-true Firebase rule" % release._n(rel_state.rule_files, "rule file")),
        release._summary_row(rel_state.files_scanned, "" if rel_state.rule_files else "; no SQL or security-rules file among them"))
    counter = {}
    for name in sorted(set(ov.tables) - set(rel_state.tables) - rel_state.rls_enabled - ov.rls_enabled - ov.loop_credited):
        if release._cap(counter, "table-without-rls"):
            path, line = ov.tables[name]
            ov.add("table-without-rls", path, line, _name("table", name in ov.code_tables), source="sql")
    # text inside a string or comment never turns RLS on: a table 0.3.2 credited from such an enable alone
    for name in sorted(set(rel_state.tables) & rel_state.rls_enabled - ov.rls_enabled - ov.loop_credited):
        if release._cap(counter, "table-without-rls"):
            path, line = rel_state.tables[name]
            ov.add("table-without-rls", path, line, _name("table", name in ov.code_tables), source="sql")
    if ov.rule_files == 0 and result["questions"]["q3"]["answer"] == "nothing-found":
        ov.add("no-rule-statements", "", 0, "no SQL file creates a table or policy; no rules file")
    stopline_pass(ov, opts, clock, end)  # it never makes the checks above unfinished
    key_pass(ov, opts, rel_state, clock, end)  # after the stop-line pass, so its rows are never fewer than main's (S-064)

# ------------------------------------------------------------------ the code inventory (--inventory, 0.6.0)
# One JSON line: every code file the agent may Read, with its line count and two marks, server files and
# handler files first. Paths and counts only, never content. The scan's own output does not change.

INVENTORY_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro", ".html", ".py", ".rb",
                  ".go", ".java", ".kt", ".php", ".cs", ".swift", ".dart", ".sql", ".prisma", ".graphql"}  # SKILL.md rule 2's list
INVENTORY_HINT = "Could not list the app's code files. The check still runs; the report says how many files it read."
SERVER_DIR_SEGMENTS = {"api", "server", "functions", "workers"}  # at any depth: app/api, pages/api, src/app/api, supabase/functions, server
SUPABASE_FROM_LINES = 8  # a `.from('t')` reaches a write verb this many lines below it (a chain split across lines)
_WRITE_VERB = r"(?:POST|PUT|PATCH|DELETE)"
_HTTP_VERB = r"(?:GET|HEAD|OPTIONS|POST|PUT|PATCH|DELETE)"
_NOT_A_MODEL = r"(?!(?:Object|Array|Promise|Reflect|Map|Set|WeakMap|Date|JSON|Math|Response|Request|URL|Buffer|String|Number|Symbol|Error)\.)"
# Each pattern reads one line, with bounded repeats only, so a 1 MB line costs one linear pass per pattern.
HANDLER_LINE_RES = (
    re.compile(r"\.rpc\(\s{0,5}['\"`]"),  # Supabase
    re.compile(r"\bprisma\.\w{1,60}\.(?:create|createMany|update|updateMany|upsert|delete|deleteMany)\("),  # Prisma
    re.compile(r"\b(?:db|tx|trx)\.(?:insert|update|delete)\("),  # Drizzle
    re.compile(r"\b(?:db|tx)\.\w{1,60}\.(?:insert|insertOne|insertMany|update|updateOne|updateMany|upsert|delete|deleteOne|deleteMany|create)\("),  # db.<table>.
    re.compile(r"\b" + _NOT_A_MODEL + r"[A-Z]\w{0,60}\.(?:create|insertMany|bulkCreate|updateOne|updateMany|findByIdAndUpdate|findOneAndUpdate"
               r"|findByIdAndDelete|findOneAndDelete|findByIdAndRemove|deleteOne|deleteMany|destroy|upsert)\("),  # Mongoose, Sequelize
    re.compile(r"\b(?:knex|db|trx)\(\s{0,5}['\"`][\w.]{1,60}['\"`]\s{0,5}\)\s{0,5}\.(?:insert|update|upsert|del|delete)\("),  # Knex
    re.compile(r"['\"`]\s{0,5}(?:insert\s{1,5}into|delete\s{1,5}from|update\s{1,5}[\w.\"]{1,60}\s{1,5}set)\b", re.I),  # SQL in a string, sql``
    re.compile(r"\b(?:setDoc|updateDoc|deleteDoc|addDoc)\("),  # Firebase
    re.compile(r"\bstripe\.[\w.]{1,60}\.(?:create|update|del)\(|\bstripe\.refunds\."),  # payments
    re.compile(r"^\s{0,40}export\s{1,5}(?:async\s{1,5})?function\s{1,5}" + _WRITE_VERB + r"\b"),  # Next.js route handlers
    re.compile(r"^\s{0,40}export\s{1,5}(?:const|let|var)\s{1,5}" + _WRITE_VERB + r"\s{0,5}="),
    re.compile(r"^\s{0,40}export\s{0,5}\{[^}\n]{0,300}\bas\s{1,5}" + _WRITE_VERB + r"\b"),
    re.compile(r"\b(?:app|router|server|fastify)\.(?:post|put|patch|delete)\s{0,5}\("),  # Express, Fastify, Hono
    re.compile(r"^\s{0,40}@[\w.]{1,60}\.(?:post|put|patch|delete)\("),  # FastAPI, Flask
)
SERVER_LINE_RES = (
    re.compile(r"^\s{0,40}['\"]use server['\"]"),  # a server action is both
    re.compile(r"^\s{0,40}import\b[^\n]{0,200}['\"](?:next/(?:headers|server|cache)|server-only)['\"]"),
    re.compile(r"^\s{0,40}export\s{1,5}(?:async\s{1,5})?function\s{1,5}" + _HTTP_VERB + r"\b"),
    re.compile(r"^\s{0,40}export\s{1,5}(?:const|let|var)\s{1,5}" + _HTTP_VERB + r"\s{0,5}="),
    re.compile(r"^\s{0,40}export\s{0,5}\{[^}\n]{0,300}\bas\s{1,5}" + _HTTP_VERB + r"\b"),
    re.compile(r"\b(?:app|router|server|fastify)\.(?:get|post|put|patch|delete|all|use)\s{0,5}\("),
    re.compile(r"^\s{0,40}@[\w.]{1,60}\.(?:get|post|put|patch|delete|route|api_route)\("),
)
USE_SERVER_RE = SERVER_LINE_RES[0]
SUPABASE_FROM_RE = re.compile(r"\.from\(\s{0,5}['\"`]")
SUPABASE_WRITE_RE = re.compile(r"\.(?:insert|update|upsert|delete)\(")


class InventoryTimeout(Exception):
    """The inventory ran past --deadline-s (the scan's own deadline)."""


def _server_path(rel):
    parts = rel.lower().split("/")
    return bool(SERVER_DIR_SEGMENTS.intersection(parts[:-1])) or bool(release.SERVER_FILE_RE.search(parts[-1]))


def _marks(text, clock, end):
    """(server, handler) from the text, one line at a time."""
    server = handler = False
    from_line = None
    for i, line in enumerate(text.split("\n")):
        if i % 1000 == 999 and clock() > end:
            raise InventoryTimeout()
        if not handler:
            m = SUPABASE_FROM_RE.search(line)
            if m:
                from_line = i
                handler = bool(SUPABASE_WRITE_RE.search(line, m.end()))
            elif from_line is not None and i - from_line <= SUPABASE_FROM_LINES and SUPABASE_WRITE_RE.search(line):
                handler = True
            if not handler and any(r.search(line) for r in HANDLER_LINE_RES):
                handler = True
        if not server and any(r.search(line) for r in SERVER_LINE_RES):
            server = True
        if USE_SERVER_RE.search(line):
            handler = True
        if server and handler:
            break
    return server, handler


def _line_count(data):
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def _listable(rel):
    """A path is printed only whole, as the agent can Read it: no control or format characters, not clipped, and no
    named key or JWT in it (that file is counted, not listed). Long plain names stay listed: the scan's token-run
    redaction would hide every timestamped migration, and the agent's own file tools show these names anyway."""
    return (len(rel) <= release.MAX_PATH_CHARS and not release.CONTROL_RE.search(rel) and release._drop_format_chars(rel) == rel
            and not release.NAMED_KEY_FULL_RE.search(rel) and not any(release.find_jwts(rel))
            and not release.PRIVATE_KEY_RE.search(rel))


def inventory_walk(real_repo, opts, clock, end):
    """Yield (rel, full, size) for each code file, with the overlay walk's rules: realpath containment, linked folders
    and files skipped, never-open folders and files skipped (not even named), EXCLUDED_DIRS plus --exclude-dir,
    hard links and special files skipped, generated and precompressed files skipped, MAX_DIR_ENTRIES."""
    for dirpath, dirnames, filenames in os.walk(real_repo, topdown=True, followlinks=False, onerror=lambda e: None):
        if clock() > end:
            raise InventoryTimeout()
        rel_dir = os.path.relpath(dirpath, real_repo).replace(os.sep, "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        real_dir = os.path.realpath(dirpath)
        if real_dir != real_repo and not real_dir.startswith(real_repo + os.sep):
            dirnames[:] = []
            continue
        parent_name = os.path.basename(dirpath)
        if len(dirnames) + len(filenames) > release.MAX_DIR_ENTRIES:
            dirnames[:] = sorted(dirnames, key=release._walk_key)[:release.MAX_DIR_ENTRIES]
            filenames = sorted(filenames)[:max(0, release.MAX_DIR_ENTRIES - len(dirnames))]
        keep = []
        for d in sorted(dirnames, key=release._walk_key):
            low = d.lower()
            if low in release.EXCLUDED_DIRS or low in opts.excluded or release.is_never_open_dir(d, parent_name):
                continue
            try:
                if os.path.islink(os.path.join(dirpath, d)):
                    continue
            except OSError:
                continue
            keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            ext = os.path.splitext(name)[1].lower()
            if ext not in INVENTORY_EXTS or name == ".git" or release.is_never_open_file(name) or NEVER_OPEN_SECRET_FILE_RE.match(name):
                continue
            if release.is_generated(name):
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
                continue
            yield (rel_dir + "/" + name) if rel_dir else name, full, st.st_size


def inventory(repo, opts, clock=time.monotonic):
    """The --inventory result: code_files counts every code file; files lists [path, lines, server, handler]
    (lines None when the file was not read: over --max-file-bytes or past the scan's file or byte caps), server
    or handler files first, then path order, cut from the end to fit MAX_OUTPUT_BYTES (truncated true)."""
    end = clock() + opts.deadline_s
    real_repo = os.path.realpath(repo)
    rows = []
    count = 0
    read_files = 0
    read_bytes = 0
    for rel, full, size in inventory_walk(real_repo, opts, clock, end):
        count += 1
        if not _listable(rel):
            continue
        server_path = _server_path(rel)
        lines, server, handler = None, server_path, False
        if size <= opts.max_file_bytes and read_files < opts.max_files and read_bytes + size <= opts.max_total_bytes:
            opened = release.open_regular(full)
            if opened is not None:
                fd, real_size = opened
                try:
                    data = release.read_bytes(fd, real_size) if real_size <= opts.max_file_bytes else None
                finally:
                    os.close(fd)
                if data is not None:
                    read_files += 1
                    read_bytes += len(data)
                    lines = _line_count(data)
                    if not rel.lower().endswith(".sql"):  # a migration's insert is not a request handler
                        s, handler = _marks(data.decode("utf-8", "replace"), clock, end)
                        server = server or s
        rows.append([rel, lines, int(server), int(handler)])
    rows.sort(key=lambda r: (0 if (r[2] or r[3]) else 1, r[0]))
    out = {"ok": True, "version": __version__, "code_files": count, "files": rows, "truncated": False}
    size = len(inventory_json(out))
    if size > release.MAX_OUTPUT_BYTES:
        out["truncated"] = True
        size += len("true") - len("false")
        while rows and size > release.MAX_OUTPUT_BYTES:
            size -= len(json.dumps(rows.pop(), ensure_ascii=True, separators=(",", ":"))) + (1 if rows else 0)
    return out


def inventory_json(inv):
    return json.dumps(inv, ensure_ascii=True, separators=(",", ":"))


def inventory_envelope(code):
    return {"ok": False, "error": code, "hint": INVENTORY_HINT, "docs": _DOCS, "partial": True}

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
    """One question's merged state: 0.3.2's rows (after the nothing-found row is gone), the overlay's rows after
    them, and the answer. 0.3.2's Q1 evidence-only rows are withheld only
    while overlay No rows are shown in their place (_shown_base), so a No the size loop trims gives its row back."""
    __slots__ = ("base_answer", "answer", "base_rows", "ov_rows", "unfinished_row", "extra", "rows_changed")


def _changed(p):
    return p.answer != p.base_answer or bool(p.ov_rows) or p.unfinished_row is not None or p.rows_changed


def _shown_base(p):
    """0.3.2's rows as shown: on Q1, one evidence-only row (last first) per overlay No row past MAX_EVIDENCE,
    0.3.2's own ScanState.add rule, plus any the size loop displaced for a No it still shows. A 0.3.2 No row is
    never displaced."""
    n_no = sum(1 for r in p.ov_rows if r["_no"])
    if not n_no:
        return p.base_rows
    need = max(0, len(p.base_rows) + n_no + (1 if p.unfinished_row else 0) - release.MAX_EVIDENCE) + p.extra
    shown = list(p.base_rows)
    for i in range(len(shown) - 1, -1, -1):
        if need <= 0:
            break
        if _evidence_only(shown[i]):
            del shown[i]
            need -= 1
    return shown


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
            no = r["_effect"] == "no" and r["_source"] in NO_SOURCES and q == "q1"  # the clamp: no other overlay row is a No
            if (r["check"], r["path"], r["line"]) in taken or (not no and q != "q10" and (r["path"], r["line"]) in lines):
                continue  # 0.3.2 already shows this line on this question (Q10: dedupe is by path, line and term)
            rows.append(dict(r, _no=no))
        rows.sort(key=lambda r: 0 if r["_no"] else 1)
        done = ov.finished and (q != "q1" or ov.key_finished)  # the key pass has its own flag; it moves Q1 only (G2)
        want = "no" if any(r["_no"] for r in rows) else ("dont-know" if rows or ov.gaps[q] or not done else "nothing-found")
        p = _Plan()
        p.base_answer, p.extra, p.rows_changed = qd["answer"], 0, False
        base = qd["answer"]
        if q == "q3" and ov.finished and ov.loop_credited:
            base, base_rows, p.rows_changed = _credit_loop_tables(ov, base, base_rows)
        p.answer = want if RANK[want] > RANK[base] else base
        if p.answer != base and base == "nothing-found":
            base_rows = [r for r in base_rows if not r["check"].startswith("nothing-found-")]
            p.rows_changed = True
        p.base_rows = base_rows
        p.unfinished_row = _unfinished_row(ov.status if not ov.finished else "unfinished") if not done and p.base_answer == "nothing-found" else None
        # Nos first: each takes one evidence-only 0.3.2 slot when Q1 is full; cautions only take free slots
        displaceable = sum(1 for r in base_rows if _evidence_only(r))
        free = max(0, cap - len(base_rows) - (1 if p.unfinished_row else 0))
        nos = [r for r in rows if r["_no"]][:free + displaceable]
        p.ov_rows = nos + [r for r in rows if not r["_no"]][:max(0, free - len(nos))]
        plans[q] = p
    return plans


def _credit_loop_tables(ov, answer, rows):
    """S-044, the one place the overlay removes a 0.3.2 row: 0.3.2's `table-without-rls` rows for tables a DO-block
    loop turned RLS on for go; tables past 0.3.2's cap of five take their places, in 0.3.2's order. The answer
    moves only when 0.3.2's Don't know rested on those rows alone, and then only to what 0.3.2 itself would say."""
    credited = set(release.sanitize(n) for n in ov.loop_credited)
    kept = [r for r in rows if not (r["check"] == "table-without-rls" and r["snippet"] in credited)]
    if len(kept) == len(rows):
        return answer, rows, False
    shown = set(r["snippet"] for r in kept if r["check"] == "table-without-rls")
    n_tables = len(shown)
    for name, path, line in ov.release_open_tables:
        if n_tables >= release.MAX_TABLE_WITHOUT_RLS_ROWS or len(kept) >= release.MAX_EVIDENCE:
            break
        if release.sanitize(name) not in shown:
            kept.append({"path": release.sanitize_path(path), "line": int(line), "snippet": release.sanitize(name), "check": "table-without-rls"})
            n_tables += 1
    if answer == "dont-know" and not kept:
        found, summary = ov.release_q3_rows
        return ("nothing-found", [found], True) if ov.release_q3_clean else ("dont-know", [summary], True)
    return answer, kept, True


def _assemble(result, plans):
    out = copy.deepcopy(result)
    for q, p in plans.items():
        if not _changed(p):
            continue
        evidence = _shown_base(p) + [_public(r) for r in p.ov_rows] + ([p.unfinished_row] if p.unfinished_row else [])
        qd = out["questions"][q]
        qd["answer"] = p.answer
        qd["evidence"] = evidence
        if q != "q10":  # Q10's confidence is 0.3.2's
            qd["confidence"] = _confidence(q, p.answer, evidence)
    return out


def _compact(row):
    if row["_no"]:
        return dict(row, snippet="", path=row["path"].rsplit("/", 1)[-1][:40])
    return dict(row, snippet="", path="", line=0)


def _fit(result, plans):
    """Keep the output under 0.3.2's cap without touching a 0.3.2 row of any other question and without ever
    setting partial: drop overlay rows that did not change an answer, then on a question the overlay moved keep
    only its No row (one) or else one row (the unfinished row counts as that one), compact what is left, then (Q1
    No only) displace 0.3.2's evidence-only Q1 rows, compact the No row fully, and as a last step demote it once.
    An overlay No that moved Q1 keeps its row while the answer stays No; where 0.3.2 already said No, the overlay's
    No row trims like any other, and a dropped No gives back the 0.3.2 row it displaced."""
    cap = release.MAX_OUTPUT_BYTES

    def over():
        return _size(_assemble(result, plans)) > cap

    if not over():
        return _assemble(result, plans)
    moved = lambda p: p.answer != p.base_answer
    # 0. stop-line rows before any row main prints (review round 1): those whose term another shown row names, then
    #    the rest, last first. stats.stopline_rows_capped counts each term no kept row names, so the verdict ticks.
    q10 = plans["q10"]
    while over() and q10.ov_rows:
        shown = [shared.stopline_terms(r["snippet"]) for r in _shown_base(q10)] + [[r["snippet"]] for r in q10.ov_rows]
        repeat = [i for i, r in enumerate(q10.ov_rows) if sum(r["snippet"] in t for t in shown) > 1]
        q10.ov_rows.pop(repeat[-1] if repeat else -1)
    # Nos sort first in ov_rows, so pop() takes cautions before any No.
    # 1. overlay rows on questions whose answer the overlay did not change, the longest list first; a No dropped
    #    here (0.3.2 already said No) gives back the 0.3.2 row it displaced
    while over():
        idle = [p for p in plans.values() if not moved(p) and p.ov_rows]
        if not idle:
            break
        max(idle, key=lambda p: len(p.ov_rows)).ov_rows.pop()
    # 2. on moved questions: cautions go while a No stays, then down to one No; otherwise down to one row (the
    #    unfinished row is that one when present)
    while over():
        busy = []
        for p in plans.values():
            if not moved(p):
                continue
            n_no = sum(1 for r in p.ov_rows if r["_no"])
            if n_no and (n_no > 1 or len(p.ov_rows) > n_no):
                busy.append(p)
            elif not n_no and len(p.ov_rows) > (0 if p.unfinished_row else 1):
                busy.append(p)
        if not busy:
            break
        max(busy, key=lambda p: len(p.ov_rows)).ov_rows.pop()
    # 3. compact what is left
    if over():
        for p in plans.values():
            p.ov_rows = [_compact(r) for r in p.ov_rows]
    q1 = plans["q1"]
    # 4. a Q1 No: displace 0.3.2's evidence-only Q1 rows, last first; then a fully compact No row
    while over() and any(r["_no"] for r in q1.ov_rows):
        before = len(_shown_base(q1))
        q1.extra += 1
        if len(_shown_base(q1)) == before:
            q1.extra -= 1
            break
    if over() and any(r["_no"] for r in q1.ov_rows):
        q1.ov_rows = [dict(r, path="", line=0, snippet="") if r["_no"] else r for r in q1.ov_rows]
    # 5. demote the overlay's No, once
    if over() and any(r["_no"] for r in q1.ov_rows):
        no_row = [r for r in q1.ov_rows if r["_no"]][0]
        q1.extra = 0
        if q1.base_answer == "nothing-found":
            q1.answer = "dont-know"
            q1.ov_rows = [_compact(dict(no_row, _no=False))]
        else:
            q1.answer = q1.base_answer
            q1.ov_rows = []
    if over():
        return None  # the caller falls back to 0.3.2's result with Nothing found withheld
    return _assemble(result, plans)


def fallback(result, status):
    """0.3.2's result with Q1/Q3/Q9 Nothing found withheld: the overlay's answer when it could not run or merge."""
    out = copy.deepcopy(result)
    out["stats"]["overlay_fallback"] = status if status in UNFINISHED_SNIPPETS else "error"
    for q in QS:
        qd = out["questions"][q]
        if qd["answer"] == "nothing-found":
            qd["answer"] = "dont-know"
            qd["evidence"] = [_unfinished_row(status if status in UNFINISHED_SNIPPETS else "error")]
            qd["confidence"] = _confidence(q, "dont-know", qd["evidence"])
    return out


def merge(result, ov):
    """0.3.2's result (deep-copied) and the overlay's findings -> the 0.3.3 result. Answers only move toward
    caution, except the S-044 DO-loop credit on Q3 (`_credit_loop_tables`); 0.3.2's rows stay first; partial,
    stats and every other question are 0.3.2's."""
    for q in QS:
        for r in ov.rows[q]:
            if r["check"] not in OVERLAY_CHECKS and r["check"] not in release.CHECKS:
                raise ValueError("unknown overlay check: " + r["check"])
    why = ov.status if not ov.finished else "full"  # a finished pass falls back only because its rows did not fit
    if _size(result) > release.MAX_OUTPUT_BYTES:
        # stop-line rows that cannot fit are counted (stopline_stat), so they alone never force the fallback
        return result if ov.finished and not any(ov.rows[q] or ov.gaps[q] for q in QS if q != "q10") else fallback(result, why)
    out = _fit(result, _plans(result, ov))
    return out if out is not None else fallback(result, why)


def stopline_stat(out, ov):
    """stats.stopline_rows_capped: how many stop-line terms the scan found that no kept Q10 row names (row cap,
    byte cap, fallback). The verdict ticks the stop-line when it is above 0. Returns out."""
    kept = set()
    for r in out["questions"]["q10"]["evidence"]:
        kept.update(shared.stopline_terms(r["snippet"]))
    out["stats"]["stopline_rows_capped"] = len(ov.stopline_found - kept)
    return out

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
    result["stats"]["overlay_fallback"] = None  # X5: why the overlay's result was not used; sized in from the start
    result["stats"]["stopline_rows_capped"] = 0  # S-062: stop-line terms no kept row names; sized in from the start
    if os.environ.get("CUSTODY_CHECK_OVERLAY") == "0":
        result["stats"]["overlay_fallback"] = "skipped"
        return _under_cap(result), state, "skipped", 0
    _under_cap(result)
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
    if not ov.finished:
        out["stats"]["overlay_fallback"] = ov.status  # unfinished or error: no DO-loop credit, some tables may show as open
    scan_with_overlay.last = ov  # for the tests: how the pass ended and what it found
    out = stopline_stat(out, ov)
    for _ in range(3):  # 0.3.2's own trim may drop a Q10 row, and a longer count may need one more trim
        if _size(out) <= release.MAX_OUTPUT_BYTES:
            break
        out = stopline_stat(_under_cap(out), ov)
    return out, state, ov.status, int((clock() - now) * 1000)


def _under_cap(result):
    """The X5 stat adds a few bytes to 0.3.2's output; past the cap, 0.3.2's own trim runs (rows go, never a No first)."""
    return release._fit_output(result) if _size(result) > release.MAX_OUTPUT_BYTES else result


def scan(repo, **kwargs):
    if release is None or shared is None:
        raise ReleaseUnavailable(RELEASE_ERROR if release is None else SHARED_ERROR)
    opts = release.Options(**kwargs)
    return scan_with_overlay(repo, opts)[0]

# ------------------------------------------------------------------ CLI (0.3.2's main, through the overlay)

def main(argv=None):
    warnings.simplefilter("ignore")  # stderr carries exactly one summary line
    argv = list(sys.argv[1:] if argv is None else argv)
    pretty = "--pretty" in argv
    exit_code = "--exit-code" in argv
    listing = "--inventory" in argv  # a failed inventory always exits non-zero: the SKILL then takes the degraded line
    fail = 2 if (exit_code or listing) else 0
    if release is None or shared is None:  # a missing release wins over a missing shared file
        out = release_envelope(RELEASE_ERROR if release is None else SHARED_ERROR)
        sys.stdout.write((json.dumps(out, ensure_ascii=True, indent=2) if pretty else json.dumps(out, ensure_ascii=True, separators=(",", ":"))) + "\n")
        sys.stdout.flush()
        return fail
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
    parser.add_argument("--inventory", action="store_true", help="list the code files instead of scanning")
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
            return fail
        repo = os.path.realpath(raw_repo)
        if not os.path.exists(repo):
            r.emit(r.envelope("repo-not-found"), pretty)
            return fail
        if not os.path.isdir(repo):
            r.emit(r.envelope("repo-not-a-directory"), pretty)
            return fail
        if not os.access(repo, os.R_OK | os.X_OK):
            r.emit(r.envelope("repo-unreadable"), pretty)
            return fail
        try:
            real_cwd = os.path.realpath(os.getcwd())
        except OSError:
            real_cwd = ""
        if real_cwd and real_cwd != repo and real_cwd.startswith(repo + os.sep):
            r.emit(r.envelope("repo-contains-cwd"), pretty)  # `..` from inside the app would walk everything above it
            return fail
        opts = r.Options(max_files=args.max_files, max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes,
                         deadline_s=args.deadline_s, exclude_dirs=args.exclude_dir, browser_prefixes=args.browser_prefix)
        if args.inventory:
            try:
                inv = inventory(repo, opts)
            except InventoryTimeout:
                r.emit(inventory_envelope("inventory-error:deadline"), pretty)
                return fail
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                r.emit(inventory_envelope("inventory-error:" + type(exc).__name__), pretty)
                return fail
            r.emit(inv, pretty)
            sys.stderr.write("custody-check v%s: inventory %d code files, %d listed%s, %d ms\n" % (
                __version__, inv["code_files"], len(inv["files"]), " (truncated)" if inv["truncated"] else "", int((time.monotonic() - started) * 1000)))
            return 0
        result, state, status, overlay_ms = scan_with_overlay(repo, opts)
        r.emit(result, pretty)
        skipped = sum(state.stats[k] for k in ("files_skipped_oversize", "files_skipped_binary", "files_skipped_generated", "files_never_open", "files_skipped_special"))
        sys.stderr.write("custody-check v%s: scanned %d, skipped %d, errored %d, %d ms; checks 0.3.3: %s, %d ms\n" % (
            __version__, state.files_scanned, skipped, state.stats["files_errored"], int((time.monotonic() - started) * 1000),
            status + (" (key pass unfinished)" if status == "finished" and not getattr(getattr(scan_with_overlay, "last", None), "key_finished", True) else ""), overlay_ms))
        return 3 if (exit_code and result["partial"]) else 0
    except r.UsageError:
        r.emit(r.envelope("usage"), pretty)
        return fail
    except SystemExit:
        raise
    except Exception as exc:  # last resort: never a traceback, never a path
        try:
            r.emit(r.envelope("internal:" + type(exc).__name__), pretty)
        except Exception:
            pass
        return fail


if __name__ == "__main__":
    sys.exit(main())
