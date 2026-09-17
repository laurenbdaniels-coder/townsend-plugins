#!/usr/bin/env python3
"""custody_scan.py: read-only evidence gatherer for the eleven custody questions.

Runs on python 3.9+ with the standard library only. Reads a repository (never
its instruction files), never writes, never talks to the network, and prints one
JSON line whose strings have all been through a redaction sweep. Exit code 0
always, unless --exit-code is given.

Run it from the folder that CONTAINS the app:  python3 -I custody_scan.py --repo ./my-app
"""
import sys

__version__ = "0.1.0"

HINTS = {
    "usage": ("Pass the app folder with --repo. Run from the folder that contains your app: python3 custody_scan.py --repo my-app", "README.md#when-it-goes-wrong"),
    "repo-not-found": ("The --repo folder was not found. Run from the folder that contains your app and pass its name.", "README.md#when-it-goes-wrong"),
    "repo-not-a-directory": ("The --repo path is a file, not a folder. Pass the app folder itself.", "README.md#when-it-goes-wrong"),
    "repo-unreadable": ("The --repo folder cannot be read. Check its permissions or copy the app somewhere you own.", "README.md#when-it-goes-wrong"),
    "python-too-old": ("This scanner needs python 3.9 or newer. Run python3 --version; on macOS install the Command Line Tools, on Windows use py -3.", "README.md#python"),
    "internal": ("The scanner hit an unexpected error. Answer the eleven questions by hand and file an issue with the error code.", "README.md#when-it-goes-wrong"),
}


def version_guard(version_info):
    """Return a failure envelope when the interpreter is too old, else None."""
    if tuple(version_info[:2]) < (3, 9):
        hint, docs = HINTS["python-too-old"]
        return {"ok": False, "error": "python-too-old", "hint": hint, "docs": docs, "partial": True}
    return None


_guard = version_guard(sys.version_info)
if _guard is not None and __name__ == "__main__":  # pragma: no cover
    import json as _json
    sys.stdout.write(_json.dumps(_guard, separators=(",", ":")) + "\n")
    sys.exit(0)

import argparse
import base64
import json
import os
import re
import shutil
import stat
import subprocess
import time
import warnings

warnings.simplefilter("ignore")

# ----------------------------------------------------------------- constants

EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "vendor", "venv", ".venv", "__pycache__", "coverage"}
NEVER_OPEN_DIRS = {".claude", ".codex", ".agents", ".windsurf", ".clinerules"}
NEVER_OPEN_DIR_PAIRS = {(".cursor", "rules"), (".github", "instructions")}
NEVER_OPEN_FILE_RE = re.compile(r"^(?:claude|agents|gemini|copilot-instructions)(?:[.-][^/]*)?\.md$", re.I)
NEVER_OPEN_FILES = {".cursorrules", ".windsurfrules", ".clinerules"}
SKIP_BASENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "cargo.lock", "composer.lock", "gemfile.lock"}
SKIP_EXT_SUFFIXES = (".map", ".min.js", ".min.css", ".bundle.js")
BROWSER_PREFIXES = ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "EXPO_PUBLIC_", "PUBLIC_", "NUXT_PUBLIC_", "GATSBY_")
ENV_TEMPLATE_NAMES = {".env.example", ".env.sample", ".env.template"}
CLIENT_TOP_DIRS = {"src", "app", "pages", "components", "public", "static"}
SERVER_SEGMENTS = {"api", "server"}
NEUTRAL_SEGMENTS = {"lib", "utils", "services", "db", "scripts", "workers", "jobs", "cron"}
SERVER_FILE_RE = re.compile(r"^middleware\.[^/]+$|\.server\.[^./]+$|^route\.[jt]s$|^\+server\.[jt]s$")
DEPLOY_CONFIG_BASENAMES = {"vercel.json", "netlify.toml", "fly.toml", "render.yaml", "render.yml", "railway.json", "dockerfile", "procfile"}
IGNORED_ENV_NAMES = {"development", "dev", "local", "test", "testing", "default", "example", "sample", "template"}
SQL_LIKE_EXTS = {".sql", ".psql", ".pgsql", ".ddl"}
DOC_EXTS = {".md", ".mdx", ".txt", ".rst"}
CODE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".py", ".rb", ".go", ".java", ".kt", ".php", ".cs", ".swift", ".dart"}
SCHEMA_EXTS = {".prisma", ".graphql", ".gql"}
HTML_EXTS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
MAX_EVIDENCE = 25
MAX_SNIPPET = 120
MAX_HITS_PER_FILE_PER_CHECK = 5
MAX_PATH_CHARS = 200
BINARY_SNIFF_BYTES = 8192
MCP_MAX_BYTES = 65536
MCP_MAX_DEPTH = 64
MCP_MAX_NODES = 10000
GIT_BUDGET_S = 15.0
ENV_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# effects: evidence < hint < yes-part < no
CHECKS = {
    "tracked-env-file": ("q1", "no"), "env-file-on-disk": ("q1", "evidence"),
    "mcp-token": ("q1", "no"), "mcp-token-shaped": ("q1", "evidence"),
    "browser-prefix-service-or-secret-name": ("q1", "no"), "browser-prefix-named-key": ("q1", "no"),
    "browser-prefix-privileged-jwt": ("q1", "no"), "browser-prefix-anon-jwt": ("q1", "evidence"),
    "browser-prefix-authenticated-jwt": ("q1", "evidence"), "browser-prefix-unknown-role-jwt": ("q1", "evidence"),
    "browser-prefix-public-key": ("q1", "evidence"), "browser-prefix-token-shaped": ("q1", "evidence"),
    "client-key-literal": ("q1", "no"), "client-privileged-jwt": ("q1", "no"), "client-secret-name-token": ("q1", "no"),
    "client-anon-jwt": ("q1", "evidence"), "client-authenticated-jwt": ("q1", "evidence"), "client-unknown-role-jwt": ("q1", "evidence"),
    "client-secret-ident-token": ("q1", "no"), "client-keyish-ident-token": ("q1", "evidence"),
    "server-path-key-literal": ("q1", "evidence"), "non-client-key-literal": ("q1", "evidence"),
    "placeholder-key-literal": ("q1", "evidence"), "test-path-key-literal": ("q1", "evidence"),
    "scan-summary": ("q1", "evidence"),
    "api-route-dir": ("q2", "hint"), "framework-config": ("q2", "hint"),
    "rls-disabled": ("q3", "no"), "policy-using-true": ("q3", "no"), "policy-with-check-true": ("q3", "evidence"),
    "policy-to-anon": ("q3", "evidence"), "storage-bucket-public-sql": ("q3", "evidence"),
    "firebase-rules-open": ("q3", "evidence"), "storage-bucket-public": ("q3", "evidence"),
    "auth-path": ("q4", "evidence"), "auth-dependency": ("q4", "evidence"),
    "deploy-config": ("q5.code", "yes-part"), "migration-path": ("q5.code", "evidence"), "backup-script": ("q5.code", "evidence"),
    "git-history": ("q5.code", "evidence"), "git-not-a-repo": ("q5.code", "evidence"), "git-unavailable": ("q5.code", "evidence"),
    "git-timeout": ("q5.code", "evidence"), "git-subdir": ("q5.code", "evidence"), "git-shallow": ("q5.code", "evidence"),
    "env-name": ("q6", "yes-part"),
    "model-env-var": ("q8", "hint"), "model-literal": ("q8", "hint"), "spend-cap-word": ("q8", "hint"), "ai-sdk-dependency": ("q8", "hint"),
    "monitoring-dependency": ("q9", "hint"), "sentry-config": ("q9", "hint"), "health-route": ("q9", "hint"), "cron-schedule": ("q9", "hint"),
    "pii-field": ("q10", "evidence"), "pii-form-input": ("q10", "evidence"),
    "builder-file": ("q11", "evidence"), "builder-dependency": ("q11", "evidence"), "builder-readme": ("q11", "evidence"), "container-config": ("q11", "evidence"),
}
QUESTION_KEYS = ["q1", "q2", "q3", "q4", "q5.code", "q5.data", "q6", "q7", "q8", "q9", "q10", "q11"]
for _name, (_q, _e) in CHECKS.items():
    assert _q in QUESTION_KEYS and _e in ("evidence", "hint", "yes-part", "no"), _name

# ------------------------------------------------------------------ regexes

TOKEN_CHARS = r"[A-Za-z0-9_\-+/=.]"
NAMED_KEY_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sb_secret_[A-Za-z0-9_-]+)(?![A-Za-z0-9_-])")
NAMED_KEY_FULL_RE = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sb_secret_[A-Za-z0-9_-]+)")
JWT_RE = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])")
JWT_RUN_RE = re.compile(r"[A-Za-z0-9_.-]{27,}")
JWT_SEG_RE = re.compile(r"[A-Za-z0-9_-]{8,}")
RUN_RE = re.compile(r"[A-Za-z0-9_\-+/=.]{20,}")
PUBLIC_KEY_RE = re.compile(r"sb_publishable_[A-Za-z0-9_-]+|pk_(?:live|test)_[A-Za-z0-9]+|AIza[0-9A-Za-z_-]{35}")
MAX_VALUE_CHARS = 8192
PUBLIC_PREFIX_RE = re.compile(r"^(?:sb_publishable_|pk_live_|pk_test_|AIza[0-9A-Za-z_-]{35})")
GENERIC_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-+/=]{32,}")
PLACEHOLDER_RE = re.compile(r"your|xxx+|placeholder|example|replace|changeme|dummy", re.I)
SENSITIVE_NAME_RE = re.compile(r"SERVICE|SECRET", re.I)
IDENT_SENSITIVE_RE = re.compile(r"service|secret", re.I)
IDENT_KEYISH_RE = re.compile(r"key|token", re.I)
IDENT_ASSIGN_TOKEN_RE = re.compile(r"\b(?P<ident>[A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*[\"'`](?P<value>[A-Za-z0-9_\-+/=.]{32,})[\"'`]")
USE_CLIENT_RE = re.compile(r"^\s*[\"']use client[\"']", re.M)
CLIENT_IMPORT_RE = re.compile(r"(?m)^\s*import\b[^\n]{0,200}\bfrom\s+[\"'](?:react|react-dom|vue|svelte|next|@sveltejs/kit)(?:/[^\"']*)?[\"']|require\([\"'](?:react|vue|svelte|next)[\"']\)")
PAGES_DATA_FN_RE = re.compile(r"\b(?:getServerSideProps|getStaticProps|getStaticPaths)\b")
TEST_PATH_RE = re.compile(r"(?:^|/)(?:__tests__|tests?|fixtures?)/|\.(?:test|spec|stories)\.[^/]+$")
RLS_DISABLED_RE = re.compile(r"disable\s+row\s+level\s+security", re.I)
USING_TRUE_RE = re.compile(r"\busing\s*\(\s*true\s*\)", re.I)
WITH_CHECK_TRUE_RE = re.compile(r"\bwith\s+check\s*\(\s*true\s*\)", re.I)
POLICY_TO_ANON_RE = re.compile(r"\bcreate\s+policy\b[^\n]{0,300}?\bto\s+anon\b", re.I)
STORAGE_BUCKET_TRUE_RE = re.compile(r"storage\.buckets\b[^\n]{0,300}?\btrue\b", re.I)
FIREBASE_ALLOW_TRUE_RE = re.compile(r"\ballow\s+[a-z, ]+:\s*if\s+true\b", re.I)
RTDB_OPEN_RE = re.compile(r"\"\.(?:read|write)\"\s*:\s*true", re.I)
TOML_PUBLIC_TRUE_RE = re.compile(r"^\s*public\s*=\s*true\b", re.I | re.M)
NETLIFY_CONTEXT_RE = re.compile(r"^\s*\[context\.([^\]\n]{1,80})\]", re.M)
WRANGLER_ENV_RE = re.compile(r"^\s*\[env\.([^\]\n]{1,80})\]", re.M)
VERCEL_ENV_RE = re.compile(r"\"(production|preview|staging)\"\s*:")
MODEL_ENV_RE = re.compile(r"\b((?:OPENAI|ANTHROPIC|CLAUDE|GEMINI|GOOGLE_AI|GOOGLE_GENERATIVE_AI|MISTRAL|COHERE|GROQ|TOGETHER|REPLICATE|HUGGINGFACE|HF|AZURE_OPENAI|OPENROUTER|XAI|DEEPSEEK|PERPLEXITY|FIREWORKS)_[A-Z0-9_]*(?:KEY|TOKEN|SECRET))\b")
MODEL_LITERAL_RE = re.compile(r"(?<![A-Za-z0-9])(?:gpt-[0-9][A-Za-z0-9.-]*|claude-[a-z0-9.-]+|gemini-[a-z0-9.-]+|llama[-_]?[0-9][A-Za-z0-9.-]*|mistral-[a-z0-9.-]+|o[134]-mini|o3)(?![A-Za-z0-9])")
SPEND_CAP_RE = re.compile(r"\b(?:max_tokens|maxTokens|rate_limit|rateLimit|spend_cap|budget_limit|maxDuration)\b")
HEALTH_ROUTE_RE = re.compile(r"[\"'`]/(?:api/)?health(?:z|check|-check)?[\"'`]")
CRON_VERCEL_RE = re.compile(r"\"crons\"\s*:")
CRON_WORKFLOW_RE = re.compile(r"^\s*-?\s*cron\s*:", re.M)
CRON_WRANGLER_RE = re.compile(r"^\s*crons\s*=", re.M)
CRON_SQL_RE = re.compile(r"cron\.schedule\(", re.I)
PII_FIELD_RE = re.compile(r"\b(email|phone|tel|ssn|social_security|dob|date_of_birth|birthdate|address|street|postal_code|zip_code|passport|credit_card|card_number|cc_number|iban|medical|diagnosis|salary)\b", re.I)
PII_INPUT_RE = re.compile(r"name=[\"'](email|tel|phone|address|street|cc-[a-z-]+|bday|ssn|dob)[\"']", re.I)
BUILDER_URL_RE = re.compile(r"lovable\.(?:dev|app)|replit\.com|bolt\.new|base44\.com|v0\.(?:dev|app)", re.I)
DEP_NAME_RE = re.compile(r"\"(@?[A-Za-z0-9_./-]+)\"\s*:")
_prefix_alt = "|".join(re.escape(p) for p in BROWSER_PREFIXES)
PREFILTER_RE = re.compile(r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sb_secret_|eyJ[A-Za-z0-9_-]{8,}|(?:[Ss]ecret|SECRET|[Ss]ervice|SERVICE|[Kk]ey|KEY|[Tt]oken|TOKEN)[A-Za-z0-9_]*\s*[:=]\s*[\"'`]|" + _prefix_alt)

AUTH_DEPS = {"next-auth", "@auth/core", "@auth/nextjs", "@clerk/nextjs", "@clerk/clerk-react", "@clerk/clerk-sdk-node", "@supabase/auth-helpers-nextjs", "@supabase/auth-helpers-react", "@supabase/ssr", "@supabase/auth-ui-react", "passport", "lucia", "better-auth", "jsonwebtoken", "jose", "firebase-admin", "@kinde-oss/kinde-auth-nextjs", "@auth0/nextjs-auth0", "auth0", "django-allauth", "devise", "flask-login", "authlib", "pyjwt", "python-jose"}
AI_DEPS = {"openai", "@anthropic-ai/sdk", "anthropic", "ai", "@ai-sdk/openai", "@ai-sdk/anthropic", "@ai-sdk/google", "langchain", "@langchain/core", "@langchain/openai", "@langchain/anthropic", "@google/generative-ai", "google-generativeai", "@google/genai", "cohere-ai", "cohere", "replicate", "@mistralai/mistralai", "mistralai", "groq-sdk", "groq", "together-ai", "litellm", "ollama", "openrouter", "@huggingface/inference", "transformers"}
MONITORING_DEPS = {"@sentry/node", "@sentry/nextjs", "@sentry/react", "@sentry/browser", "@sentry/sveltekit", "@sentry/remix", "sentry-sdk", "dd-trace", "datadog", "@datadog/browser-rum", "@logtail/node", "@logtail/next", "newrelic", "@highlight-run/next", "@highlight-run/node", "@axiomhq/js", "next-axiom", "node-cron", "cron", "bull", "bullmq", "agenda", "@vercel/cron", "pino", "winston", "better-stack"}
BUILDER_DEPS_RE = re.compile(r"^(?:lovable-tagger|@base44/sdk|@replit/.+)$")
BUILDER_BASENAMES = {".replit", "replit.nix", ".bolt", ".lovable", "base44.config.json", ".v0"}
FRAMEWORK_CONFIG_RE = re.compile(r"^(?:next|vite|nuxt|svelte|astro|remix|gatsby|angular|vue)\.config\.[a-z]+$", re.I)
API_ROUTE_PREFIXES = ("pages/api/", "app/api/", "api/", "server/", "netlify/functions/", "supabase/functions/", "functions/", "workers/")
AUTH_SEGMENTS = {"auth", "authorize", "permissions", "rbac", "guards", "policy", "policies", "middleware", "proxy"}
MONITOR_CONFIG_RE = re.compile(r"^(?:sentry\.[a-z.]*config\.[a-z]+|sentry\.properties|checkly\.config\.[a-z]+|uptimerobot[^/]*)$", re.I)
HEALTH_PATH_RE = re.compile(r"(?:^|/)health(?:z|check|-check)?(?:\.[a-z]+)?$", re.I)


class UsageError(Exception):
    pass


# ---------------------------------------------------------------- redaction

def redact_value(value):
    """Named patterns keep a 4-char prefix and the length; anything else keeps only the length."""
    if NAMED_KEY_FULL_RE.match(value) or value.startswith("eyJ") or PUBLIC_PREFIX_RE.match(value):
        return value[:4] + "…" + str(len(value))
    return "[token-shaped, %d chars]" % len(value)


def _classes(value):
    classes = sum(1 for test in (str.islower, str.isupper, str.isdigit) if any(test(c) for c in value))
    if any(c in "_-+/=" for c in value):
        classes += 1
    return classes


def _redact_piece(piece):
    piece = NAMED_KEY_RE.sub(lambda m: redact_value(m.group(0)), piece)
    piece = PUBLIC_KEY_RE.sub(lambda m: redact_value(m.group(0)), piece)
    if len(piece) >= 32 and GENERIC_TOKEN_RE.fullmatch(piece) and _classes(piece) >= 3:
        return redact_value(piece)
    return piece


def _redact_run(match):
    pieces = match.group(0).split(".")
    out = []
    i = 0
    while i < len(pieces):
        p = pieces[i]
        if p.startswith("eyJ") and len(p) >= 11 and i + 2 < len(pieces) and all(JWT_SEG_RE.fullmatch(x) for x in pieces[i:i + 3]):
            out.append(redact_value(".".join(pieces[i:i + 3])))
            i += 3
            continue
        out.append(_redact_piece(p))
        i += 1
    return ".".join(out)


def sweep(text):
    """Linear-time redaction: every token run is inspected piece by piece, never with backtracking regexes."""
    return RUN_RE.sub(_redact_run, text)


def find_jwts(text):
    """Yield (start, end) of every JWT-shaped triple, linear in the text length."""
    for m in JWT_RUN_RE.finditer(text):
        run = m.group(0)
        if len(run) > 4 * MAX_VALUE_CHARS:
            continue
        base = m.start()
        pieces = run.split(".")
        offsets = []
        pos = 0
        for p in pieces:
            offsets.append(pos)
            pos += len(p) + 1
        i = 0
        while i + 2 < len(pieces):
            p = pieces[i]
            if p.startswith("eyJ") and len(p) >= 11 and len(pieces[i + 1]) >= 8 and len(pieces[i + 2]) >= 8:
                yield base + offsets[i], base + offsets[i + 2] + len(pieces[i + 2])
                i += 3
            else:
                i += 1


def is_jwt(value):
    return len(value) <= MAX_VALUE_CHARS and bool(JWT_RE.fullmatch(value))


def sanitize(text, limit=MAX_SNIPPET):
    text = CONTROL_RE.sub("", str(text)).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = sweep(text)
    if len(text) > limit:
        text = text[:limit]
    return text


def sanitize_path(rel):
    rel = rel.replace(os.sep, "/")
    return sanitize(rel, MAX_PATH_CHARS)


def make_snippet(text, start, end):
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]
    s = start - line_start
    if len(line) > MAX_SNIPPET:
        left = max(0, s - 40)
        line = line[left:left + MAX_SNIPPET]
    return sanitize(line)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def is_generic_token(value):
    if len(value) < 32 or len(value) > MAX_VALUE_CHARS or not GENERIC_TOKEN_RE.fullmatch(value.rstrip(".")):
        return False
    return _classes(value) >= 3


def is_placeholder(value, is_jwt):
    if PLACEHOLDER_RE.search(value):
        return True
    if not is_jwt and not any(c.isdigit() for c in value):
        return True
    return False


def decode_jwt_role(token):
    try:
        parts = token.split(".")
        if len(parts) != 3 or len(parts[1]) > 4096:
            return None
        payload = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        data = json.loads(payload.decode("utf-8"))
        role = data.get("role") if isinstance(data, dict) else None
        return role if isinstance(role, str) else None
    except Exception:
        return None


# ------------------------------------------------------------------ objects

class Options(object):
    def __init__(self, max_files=20000, max_file_bytes=524288, max_total_bytes=268435456, deadline_s=120.0, exclude_dirs=(), browser_prefixes=()):
        self.max_files = int(max_files)
        self.max_file_bytes = int(max_file_bytes)
        self.max_total_bytes = int(max_total_bytes)
        self.deadline_s = float(deadline_s)
        self.exclude_dirs_added = []
        for d in exclude_dirs:
            d = str(d).strip().strip("/").lower()
            if not d or d == "." or "/" in d or d in NEVER_OPEN_DIRS or d in EXCLUDED_DIRS:
                continue
            if d not in self.exclude_dirs_added:
                self.exclude_dirs_added.append(d)
        self.browser_prefixes_added = []
        for p in browser_prefixes:
            p = str(p).strip()
            if p and p not in BROWSER_PREFIXES and p not in self.browser_prefixes_added:
                self.browser_prefixes_added.append(p)
        self.excluded = EXCLUDED_DIRS | set(self.exclude_dirs_added)
        self.prefixes = tuple(BROWSER_PREFIXES) + tuple(self.browser_prefixes_added)
        alt = "|".join(re.escape(p) for p in self.prefixes)
        self.browser_assign_re = re.compile(r"[\"']?\b(?P<name>(?:" + alt + r")[A-Z0-9_]+)[\"']?\s*[=:]\s*[\"'`]?(?P<value>[A-Za-z0-9_\-+/=.]{16,})")
        self.prefilter_re = re.compile(PREFILTER_RE.pattern + ("|" + alt if self.browser_prefixes_added else ""))


class ScanFile(object):
    __slots__ = ("rel", "abs", "base", "ext", "top", "segments", "cls", "kinds", "text")

    def __init__(self, rel, abspath, base, ext, top, segments, cls, kinds, text):
        self.rel = rel
        self.abs = abspath
        self.base = base
        self.ext = ext
        self.top = top
        self.segments = segments
        self.cls = cls
        self.kinds = kinds
        self.text = text


class ScanState(object):
    def __init__(self):
        self.files_scanned = 0
        self.partial = False
        self.git = {"commits": None, "tags": None, "shallow": None, "tracked_env_files": None}
        self.evidence = dict((k, []) for k in QUESTION_KEYS)
        self.effects = dict((k, set()) for k in QUESTION_KEYS)
        self.env_names = set()
        self.deploy_configs = []
        self.seen = set()
        self.warnings = []
        self.stats = {"files_skipped_oversize": 0, "files_skipped_binary": 0, "files_skipped_generated": 0, "files_never_open": 0,
                      "files_skipped_special": 0, "files_errored": 0, "max_files_hit": False, "max_total_bytes_hit": False, "deadline_hit": False,
                      "config": {"exclude_dirs_added": [], "browser_prefixes_added": []}}

    def add(self, check, path, line, snippet):
        question, effect = CHECKS[check]
        self.effects[question].add(effect)
        key = (check, path, line, snippet)
        if key in self.seen:
            return
        self.seen.add(key)
        if len(self.evidence[question]) < MAX_EVIDENCE:
            self.evidence[question].append({"path": sanitize_path(path), "line": int(line), "snippet": sanitize(snippet), "check": check})


def iter_questions(result):
    for key, value in result["questions"].items():
        if key == "q5":
            yield value["code"]
            yield value["data"]
        else:
            yield value


# ---------------------------------------------------------------- filesystem

def is_never_open_dir(name, parent):
    n = name.lower()
    return n in NEVER_OPEN_DIRS or (parent.lower(), n) in NEVER_OPEN_DIR_PAIRS


def is_never_open_file(base):
    b = base.lower()
    return b in NEVER_OPEN_FILES or bool(NEVER_OPEN_FILE_RE.match(b))


def is_generated(base):
    b = base.lower()
    return b in SKIP_BASENAMES or b.endswith(SKIP_EXT_SUFFIXES)


def count_files(path):
    n = 0
    for _, _, files in os.walk(path, followlinks=False, onerror=lambda e: None):
        n += len(files)
    return n


def open_regular(path):
    """Open without following symlinks; reject anything that is not a plain single-link file."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        st = os.fstat(fd)
    except OSError:
        os.close(fd)
        return None
    if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
        os.close(fd)
        return None
    return fd, st.st_size


def read_bytes(fd, size):
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = os.read(fd, min(remaining, 1 << 20))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def decode_text(data):
    """Return decoded text, or None when the file looks binary."""
    if data.startswith(b"\xff\xfe\x00\x00") or data.startswith(b"\x00\x00\xfe\xff"):
        return data.decode("utf-32", errors="replace")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        return None
    return data.decode("utf-8-sig", errors="replace")


def classify(rel, base, ext, text):
    segments = rel.split("/")
    dirs = segments[:-1]
    top = dirs[0] if dirs else ""
    lower_dirs = [d.lower() for d in dirs]
    kinds = set()
    b = base.lower()
    if re.match(r"^\.env(\..+)?$", b) or b.endswith(".env") or b == ".envrc":
        kinds.add("env-template" if b in ENV_TEMPLATE_NAMES else "env")
    if b == ".mcp.json" or (b == "mcp.json" and lower_dirs and lower_dirs[-1] == ".cursor"):
        kinds.add("mcp")
    if ext in SQL_LIKE_EXTS:
        kinds.add("sql")
    if b.endswith(".rules") or b == "database.rules.json":
        kinds.add("rules")
    if b == "config.toml" and lower_dirs and lower_dirs[-1] == "supabase":
        kinds.add("supabase-config")
    if b in ("package.json", "requirements.txt", "pyproject.toml", "gemfile", "go.mod"):
        kinds.add("manifest")
    if ext in CODE_EXTS:
        kinds.add("code")
    if ext in SCHEMA_EXTS or b in ("models.py", "schema.rb", "schema.ts", "schema.py", "schema.sql"):
        kinds.add("schema")
    if ext == ".toml":
        kinds.add("toml")
    if ext == ".json":
        kinds.add("json")
    if ext in (".yml", ".yaml"):
        kinds.add("yaml")
        if len(lower_dirs) >= 2 and lower_dirs[0] == ".github" and lower_dirs[1] == "workflows":
            kinds.add("workflow")
    if not dirs and b.startswith("readme"):
        kinds.add("readme")
    if ext in HTML_EXTS:
        kinds.add("html")
    if ext in DOC_EXTS:
        kinds.add("doc")
    cls = "other"
    if any(d in SERVER_SEGMENTS for d in lower_dirs) or SERVER_FILE_RE.search(base):
        cls = "server"
    else:
        use_client = bool(USE_CLIENT_RE.search(text[:500]))
        client_import = bool(CLIENT_IMPORT_RE.search(text))
        if any(d in NEUTRAL_SEGMENTS for d in lower_dirs):
            cls = "client" if (use_client or client_import) else "other"
        elif top.lower() == "app":
            cls = "client" if use_client else "other"
        elif top.lower() == "pages":
            cls = "other" if PAGES_DATA_FN_RE.search(text) else "client"
        elif top.lower() in CLIENT_TOP_DIRS or ext in (".vue", ".svelte") or use_client or client_import:
            cls = "client"
    return top, segments, cls, kinds


# ---------------------------------------------------------------- detectors

def _cap(counter, check):
    counter[check] = counter.get(check, 0) + 1
    return counter[check] <= MAX_HITS_PER_FILE_PER_CHECK


def detect_browser_prefix(sf, state, opts, claimed):
    text = sf.text
    counter = {}
    is_env = "env" in sf.kinds or "env-template" in sf.kinds
    is_test = bool(TEST_PATH_RE.search(sf.rel))
    for m in opts.browser_assign_re.finditer(text):
        name, value = m.group("name"), m.group("value").rstrip(".")
        value_start = m.start("value")
        claimed.append((value_start, value_start + len(value)))
        if len(value) > MAX_VALUE_CHARS:
            continue
        named = bool(NAMED_KEY_FULL_RE.match(value))
        jwt = is_jwt(value)
        generic = is_generic_token(value)
        public = bool(PUBLIC_PREFIX_RE.match(value))
        if not (named or jwt or generic or public):
            continue
        line = line_of(text, m.start())
        snippet = name if is_env else make_snippet(text, m.start(), m.end())
        if is_placeholder(value, jwt):
            check = "placeholder-key-literal"
        elif is_test and (named or jwt or generic):
            check = "test-path-key-literal"
        elif SENSITIVE_NAME_RE.search(name) and (named or jwt or generic):
            check = "browser-prefix-service-or-secret-name"
        elif named:
            check = "browser-prefix-named-key"
        elif jwt:
            role = decode_jwt_role(value)
            if role == "service_role":
                check = "browser-prefix-privileged-jwt"
            elif role == "anon":
                check = "browser-prefix-anon-jwt"
            elif role == "authenticated":
                check = "browser-prefix-authenticated-jwt"
            else:
                check = "browser-prefix-unknown-role-jwt"
        elif public:
            check = "browser-prefix-public-key"
        else:
            check = "browser-prefix-token-shaped"
        if _cap(counter, check):
            state.add(check, sf.rel, line, snippet)


def detect_key_literals(sf, state, opts, claimed):
    text = sf.text
    counter = {}
    is_env = "env" in sf.kinds or "env-template" in sf.kinds
    is_test = bool(TEST_PATH_RE.search(sf.rel))

    def overlaps(a, b):
        return any(a < e and b > s for s, e in claimed)

    hits = []
    for m in NAMED_KEY_RE.finditer(text):
        hits.append((m.start(), m.end(), "named", None))
    for start, end in find_jwts(text):
        hits.append((start, end, "jwt", None))
    for m in IDENT_ASSIGN_TOKEN_RE.finditer(text):
        value = m.group("value")
        if len(value) > MAX_VALUE_CHARS or NAMED_KEY_FULL_RE.match(value) or is_jwt(value) or not is_generic_token(value.rstrip(".")):
            continue
        hits.append((m.start("value"), m.end("value"), "generic", m.group("ident")))
    hits.sort()
    for start, end, kind, ident in hits:
        if overlaps(start, end):
            continue
        value = text[start:end]
        line = line_of(text, start)
        snippet = "" if is_env else make_snippet(text, start, end)
        if is_env:
            lstart = text.rfind("\n", 0, start) + 1
            snippet = re.split(r"[=:\s]", text[lstart:start].strip(), 1)[0][:60]
        check = None
        if kind == "generic":
            if not (IDENT_SENSITIVE_RE.search(ident) or IDENT_KEYISH_RE.search(ident)):
                continue
        if is_placeholder(value, kind == "jwt"):
            check = "placeholder-key-literal"
        elif is_test:
            check = "test-path-key-literal"
        elif sf.cls == "server":
            check = "server-path-key-literal"
        elif sf.cls == "other":
            check = "non-client-key-literal"
        elif kind == "named":
            check = "client-key-literal"
        elif kind == "jwt":
            role = decode_jwt_role(value)
            lstart = text.rfind("\n", 0, start) + 1
            if role == "service_role":
                check = "client-privileged-jwt"
            elif SENSITIVE_NAME_RE.search(text[lstart:start]):
                check = "client-secret-name-token"
            elif role == "anon":
                check = "client-anon-jwt"
            elif role == "authenticated":
                check = "client-authenticated-jwt"
            else:
                check = "client-unknown-role-jwt"
        else:
            if IDENT_SENSITIVE_RE.search(ident):
                check = "client-secret-ident-token"
            else:
                check = "client-keyish-ident-token"
        if check and _cap(counter, check):
            state.add(check, sf.rel, line, snippet)


def detect_mcp(sf, state, opts):
    text = sf.text
    if len(text) > MCP_MAX_BYTES:
        state.stats["files_skipped_oversize"] += 1
        state.partial = True
        return
    counter = {}
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        data = None
    if data is None:
        for m in NAMED_KEY_RE.finditer(text):
            if _cap(counter, "mcp-token"):
                state.add("mcp-token", sf.rel, line_of(text, m.start()), make_snippet(text, m.start(), m.end()))
        for start, end in find_jwts(text):
            if _cap(counter, "mcp-token"):
                state.add("mcp-token", sf.rel, line_of(text, start), make_snippet(text, start, end))
        return
    stack = [("", data, 0)]
    nodes = 0
    while stack:
        key, node, depth = stack.pop()
        nodes += 1
        if nodes > MCP_MAX_NODES or depth > MCP_MAX_DEPTH:
            state.partial = True
            break
        if isinstance(node, dict):
            for k, v in node.items():
                stack.append((str(k), v, depth + 1))
        elif isinstance(node, list):
            for v in node:
                stack.append((key, v, depth + 1))
        elif isinstance(node, str):
            value = node
            if len(value) > MAX_VALUE_CHARS:
                continue
            if NAMED_KEY_RE.search(value) or any(True for _ in find_jwts(value)):
                check = "mcp-token"
            elif is_generic_token(value):
                lk = key.lower()
                if IDENT_SENSITIVE_RE.search(key) or IDENT_KEYISH_RE.search(key) or lk in ("authorization", "password", "auth"):
                    check = "mcp-token"
                else:
                    check = "mcp-token-shaped"
            else:
                continue
            if _cap(counter, check):
                state.add(check, sf.rel, 0, key)


def _finditer_lines(regex, text, sf, state, check, counter, snippet_fn=None):
    for m in regex.finditer(text):
        if _cap(counter, check):
            snippet = snippet_fn(m) if snippet_fn else make_snippet(text, m.start(), m.end())
            state.add(check, sf.rel, line_of(text, m.start()), snippet)


def detect_sql(sf, state, opts):
    counter = {}
    text = sf.text
    _finditer_lines(RLS_DISABLED_RE, text, sf, state, "rls-disabled", counter)
    _finditer_lines(USING_TRUE_RE, text, sf, state, "policy-using-true", counter)
    _finditer_lines(WITH_CHECK_TRUE_RE, text, sf, state, "policy-with-check-true", counter)
    _finditer_lines(POLICY_TO_ANON_RE, text, sf, state, "policy-to-anon", counter)
    _finditer_lines(STORAGE_BUCKET_TRUE_RE, text, sf, state, "storage-bucket-public-sql", counter)
    _finditer_lines(CRON_SQL_RE, text, sf, state, "cron-schedule", counter)


def detect_rules(sf, state, opts):
    counter = {}
    _finditer_lines(FIREBASE_ALLOW_TRUE_RE, sf.text, sf, state, "firebase-rules-open", counter)
    _finditer_lines(RTDB_OPEN_RE, sf.text, sf, state, "firebase-rules-open", counter)


def detect_supabase_config(sf, state, opts):
    _finditer_lines(TOML_PUBLIC_TRUE_RE, sf.text, sf, state, "storage-bucket-public", {})


def _env_name(state, sf, name, line):
    name = name.strip().lower()
    if not ENV_NAME_RE.match(name) or name in IGNORED_ENV_NAMES:
        return
    state.env_names.add(name)
    state.add("env-name", sf.rel, line, name)


def detect_env_names(sf, state, opts):
    text = sf.text
    b = sf.base.lower()
    if b == "netlify.toml":
        for m in NETLIFY_CONTEXT_RE.finditer(text):
            _env_name(state, sf, m.group(1), line_of(text, m.start()))
    elif b == "wrangler.toml":
        for m in WRANGLER_ENV_RE.finditer(text):
            _env_name(state, sf, m.group(1), line_of(text, m.start()))
        if CRON_WRANGLER_RE.search(text):
            m = CRON_WRANGLER_RE.search(text)
            state.add("cron-schedule", sf.rel, line_of(text, m.start()), make_snippet(text, m.start(), m.end()))
    elif b == "vercel.json":
        for m in VERCEL_ENV_RE.finditer(text):
            _env_name(state, sf, m.group(1), line_of(text, m.start()))
        m = CRON_VERCEL_RE.search(text)
        if m:
            state.add("cron-schedule", sf.rel, line_of(text, m.start()), make_snippet(text, m.start(), m.end()))


def detect_manifest(sf, state, opts):
    text = sf.text
    names = set()
    if sf.base.lower() == "package.json":
        try:
            data = json.loads(text)
            for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                sec = data.get(section) if isinstance(data, dict) else None
                if isinstance(sec, dict):
                    names.update(str(k) for k in sec.keys())
        except (ValueError, RecursionError):
            names.update(DEP_NAME_RE.findall(text))
    else:
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"^([A-Za-z0-9_.@/-]+)", line)
            if m:
                names.add(m.group(1).lower())
    counter = {}
    for name in sorted(names):
        lname = name.lower()
        if lname in AUTH_DEPS and _cap(counter, "auth-dependency"):
            state.add("auth-dependency", sf.rel, 0, name)
        if lname in AI_DEPS and _cap(counter, "ai-sdk-dependency"):
            state.add("ai-sdk-dependency", sf.rel, 0, name)
        if lname in MONITORING_DEPS and _cap(counter, "monitoring-dependency"):
            state.add("monitoring-dependency", sf.rel, 0, name)
        if BUILDER_DEPS_RE.match(lname) and _cap(counter, "builder-dependency"):
            state.add("builder-dependency", sf.rel, 0, name)


def detect_model_hints(sf, state, opts):
    counter = {}
    text = sf.text
    _finditer_lines(MODEL_ENV_RE, text, sf, state, "model-env-var", counter, lambda m: m.group(1))
    _finditer_lines(MODEL_LITERAL_RE, text, sf, state, "model-literal", counter)
    _finditer_lines(SPEND_CAP_RE, text, sf, state, "spend-cap-word", counter, lambda m: m.group(0))
    _finditer_lines(HEALTH_ROUTE_RE, text, sf, state, "health-route", counter)


def detect_workflow(sf, state, opts):
    _finditer_lines(CRON_WORKFLOW_RE, sf.text, sf, state, "cron-schedule", {}, lambda m: "cron")


def detect_pii_schema(sf, state, opts):
    counter = {}
    seen = set()
    for m in PII_FIELD_RE.finditer(sf.text):
        field = m.group(1).lower()
        if field in seen:
            continue
        seen.add(field)
        if len(seen) > 3:
            break
        if _cap(counter, "pii-field"):
            state.add("pii-field", sf.rel, line_of(sf.text, m.start()), field)


def detect_pii_inputs(sf, state, opts):
    _finditer_lines(PII_INPUT_RE, sf.text, sf, state, "pii-form-input", {}, lambda m: m.group(1).lower())


def detect_readme(sf, state, opts):
    _finditer_lines(BUILDER_URL_RE, sf.text, sf, state, "builder-readme", {}, lambda m: m.group(0).lower())


def _pred_code_or_env(sf):
    return "code" in sf.kinds or "env" in sf.kinds or "env-template" in sf.kinds or "html" in sf.kinds or "toml" in sf.kinds or "yaml" in sf.kinds or ("json" in sf.kinds and "mcp" not in sf.kinds and sf.base.lower() != "package.json")


def _q1_gate(sf, opts):
    return _pred_code_or_env(sf) and bool(opts.prefilter_re.search(sf.text))


DETECTORS = [
    (lambda sf: "mcp" in sf.kinds, lambda sf, state, opts: detect_mcp(sf, state, opts)),
    (lambda sf: "sql" in sf.kinds, detect_sql),
    (lambda sf: "rules" in sf.kinds, detect_rules),
    (lambda sf: "supabase-config" in sf.kinds, detect_supabase_config),
    (lambda sf: sf.base.lower() in ("netlify.toml", "wrangler.toml", "vercel.json"), detect_env_names),
    (lambda sf: "manifest" in sf.kinds, detect_manifest),
    (lambda sf: "code" in sf.kinds or "env" in sf.kinds, detect_model_hints),
    (lambda sf: "workflow" in sf.kinds, detect_workflow),
    (lambda sf: "schema" in sf.kinds or "sql" in sf.kinds, detect_pii_schema),
    (lambda sf: "html" in sf.kinds and sf.cls == "client", detect_pii_inputs),
    (lambda sf: "readme" in sf.kinds, detect_readme),
]


def layout_checks(rel, base, state):
    lower = rel.lower()
    segments = lower.split("/")
    dirs = segments[:-1]
    b = base.lower()
    stem = b.rsplit(".", 1)[0] if "." in b else b
    if any(lower.startswith(p) for p in API_ROUTE_PREFIXES):
        state.add("api-route-dir", rel, 0, "")
    if FRAMEWORK_CONFIG_RE.match(b):
        state.add("framework-config", rel, 0, "")
    if any(d in AUTH_SEGMENTS for d in dirs) or stem in AUTH_SEGMENTS or "[...nextauth]" in lower:
        state.add("auth-path", rel, 0, "")
    is_deploy = b in DEPLOY_CONFIG_BASENAMES or (len(dirs) >= 2 and dirs[0] == ".github" and dirs[1] == "workflows" and (b.endswith(".yml") or b.endswith(".yaml"))) or re.match(r"^fly\.[a-z0-9_-]+\.toml$", b)
    if is_deploy:
        state.deploy_configs.append(rel)
        state.add("deploy-config", rel, 0, "")
    m = re.match(r"^fly\.([a-z0-9_-]+)\.toml$", b)
    if m:
        name = m.group(1)
        if name not in IGNORED_ENV_NAMES:
            state.env_names.add(name)
            state.add("env-name", rel, 0, name)
    m = re.match(r"^\.env\.([a-z0-9_-]+)$", b)
    if m and b not in ENV_TEMPLATE_NAMES:
        name = m.group(1)
        if name not in IGNORED_ENV_NAMES and ENV_NAME_RE.match(name):
            state.env_names.add(name)
            state.add("env-name", rel, 0, name)
    if any(d in ("migrations", "migration") for d in dirs) or "migrat" in b:
        state.add("migration-path", rel, 0, "")
    if "backup" in b:
        state.add("backup-script", rel, 0, "")
    if MONITOR_CONFIG_RE.match(b):
        state.add("sentry-config", rel, 0, "")
    if HEALTH_PATH_RE.search(lower):
        state.add("health-route", rel, 0, "")
    if b in BUILDER_BASENAMES or any(d in (".bolt", ".lovable", ".v0") for d in dirs):
        state.add("builder-file", rel, 0, "")
    if b == "dockerfile" or b.startswith("docker-compose") or b == "compose.yaml" or b == "compose.yml":
        state.add("container-config", rel, 0, "")


# ---------------------------------------------------------------------- git

def _darwin_git_ready():
    try:
        r = subprocess.run(["xcode-select", "-p"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return True


def _git_dir(toplevel):
    dot = os.path.join(toplevel, ".git")
    if os.path.isdir(dot):
        return dot
    try:
        with open(dot, "r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline().strip()
        if first.startswith("gitdir:"):
            target = first[len("gitdir:"):].strip()
            return target if os.path.isabs(target) else os.path.join(toplevel, target)
    except OSError:
        pass
    return dot


def git_facts(repo, state):
    real_repo = os.path.realpath(repo)
    if shutil.which("git") is None:
        state.add("git-unavailable", "", 0, "git is not installed")
        return
    if sys.platform == "darwin" and not _darwin_git_ready():
        state.add("git-unavailable", "", 0, "git needs the Xcode Command Line Tools")
        return
    base = ["git", "-c", "core.fsmonitor=", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat", "-c", "core.sshCommand=", "-c", "credential.helper=", "-C", real_repo]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    started = time.monotonic()

    def run(args):
        remaining = GIT_BUDGET_S - (time.monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, GIT_BUDGET_S)
        return subprocess.run(base + args, capture_output=True, text=True, env=env, timeout=max(1.0, remaining), stdin=subprocess.DEVNULL)

    try:
        top = run(["rev-parse", "--show-toplevel"])
        if top.returncode != 0:
            state.add("git-not-a-repo", "", 0, "not a git repository")
            return
        toplevel = os.path.realpath(top.stdout.strip())
        subdir = False
        if toplevel != real_repo:
            if real_repo.startswith(toplevel + os.sep):
                subdir = True
                tracked_here = run(["ls-files", "-z", "--", "."])
                if tracked_here.returncode != 0 or not tracked_here.stdout.strip("\0"):
                    state.add("git-not-a-repo", "", 0, "this folder is not tracked by git (an export inside another repository)")
                    return
            else:
                state.add("git-not-a-repo", "", 0, "not a git repository")
                return
        commits = run(["rev-list", "--count", "HEAD"])
        state.git["commits"] = int(commits.stdout.strip()) if commits.returncode == 0 and commits.stdout.strip().isdigit() else 0
        tags = run(["tag", "--list"])
        state.git["tags"] = len([t for t in tags.stdout.splitlines() if t.strip()]) if tags.returncode == 0 else 0
        shallow = run(["rev-parse", "--is-shallow-repository"])
        state.git["shallow"] = shallow.stdout.strip() == "true" or os.path.exists(os.path.join(_git_dir(toplevel), "shallow"))
        tracked = run(["ls-files", "-z", "--", ".env*", "*/.env*"])
        names = []
        if tracked.returncode == 0:
            for p in tracked.stdout.split("\0"):
                if not p:
                    continue
                b = p.rsplit("/", 1)[-1]
                if re.match(r"^\.env(\..+)?$", b) and b not in ENV_TEMPLATE_NAMES:
                    names.append(p)
        state.git["tracked_env_files"] = sorted(names)
        for p in state.git["tracked_env_files"]:
            state.add("tracked-env-file", p, 0, "")
        if subdir:
            state.add("git-subdir", "", 0, "the app folder is inside a larger repository")
        if state.git["shallow"]:
            state.add("git-shallow", "", 0, "shallow clone")
        state.add("git-history", "", 0, "%d commits, %d tags" % (state.git["commits"], state.git["tags"]))
    except subprocess.TimeoutExpired:
        state.git = {"commits": None, "tags": None, "shallow": None, "tracked_env_files": None}
        state.add("git-timeout", "", 0, "git did not answer in time")
    except OSError:
        state.git = {"commits": None, "tags": None, "shallow": None, "tracked_env_files": None}
        state.add("git-unavailable", "", 0, "git could not be run")


# --------------------------------------------------------------------- walk

def run_scan(repo, state, opts):
    state.stats["config"] = {"exclude_dirs_added": list(opts.exclude_dirs_added), "browser_prefixes_added": list(opts.browser_prefixes_added)}
    real_repo = os.path.realpath(repo)
    deadline = time.monotonic() + opts.deadline_s
    total_bytes = 0
    candidates = 0
    stop = False
    git_facts(repo, state)
    git_present = state.git["tracked_env_files"] is not None
    for dirpath, dirnames, filenames in os.walk(real_repo, topdown=True, followlinks=False, onerror=lambda e: None):
        if stop:
            break
        rel_dir = os.path.relpath(dirpath, real_repo).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        parent_name = os.path.basename(dirpath)
        real_dir = os.path.realpath(dirpath)
        if real_dir != real_repo and not real_dir.startswith(real_repo + os.sep):
            dirnames[:] = []
            continue
        keep = []
        for d in sorted(dirnames):
            full = os.path.join(dirpath, d)
            try:
                if os.path.islink(full):
                    state.stats["files_skipped_special"] += 1
                    continue
            except OSError:
                continue
            if is_never_open_dir(d, parent_name):
                state.stats["files_never_open"] += count_files(full)
                continue
            if d.lower() in opts.excluded:
                continue
            keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            if time.monotonic() > deadline:
                state.stats["deadline_hit"] = True
                state.partial = True
                stop = True
                break
            rel = (rel_dir + "/" + name) if rel_dir else name
            full = os.path.join(dirpath, name)
            if is_never_open_file(name):
                state.stats["files_never_open"] += 1
                continue
            if name == ".git":
                continue
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
                state.stats["files_skipped_special"] += 1
                continue
            if candidates >= opts.max_files:
                state.stats["max_files_hit"] = True
                state.partial = True
                stop = True
                break
            candidates += 1
            base = name
            ext = os.path.splitext(name)[1].lower()
            layout_checks(rel, base, state)
            if not git_present and re.match(r"^\.env(\..+)?$", name) and name not in ENV_TEMPLATE_NAMES:
                state.add("env-file-on-disk", rel, 0, "")
            if is_generated(name):
                state.stats["files_skipped_generated"] += 1
                continue
            if st.st_size > opts.max_file_bytes:
                state.stats["files_skipped_oversize"] += 1
                continue
            opened = open_regular(full)
            if opened is None:
                state.stats["files_skipped_special"] += 1
                continue
            fd, size = opened
            try:
                if size > opts.max_file_bytes:
                    state.stats["files_skipped_oversize"] += 1
                    continue
                if total_bytes + size > opts.max_total_bytes:
                    state.stats["max_total_bytes_hit"] = True
                    state.partial = True
                    stop = True
                    break
                data = read_bytes(fd, size)
            finally:
                os.close(fd)
            total_bytes += len(data)
            text = decode_text(data)
            if text is None:
                state.stats["files_skipped_binary"] += 1
                continue
            try:
                top, segments, cls, kinds = classify(rel, base, ext, text)
                sf = ScanFile(rel, full, base, ext, top, segments, cls, kinds, text)
                if _q1_gate(sf, opts):
                    claimed = []
                    detect_browser_prefix(sf, state, opts, claimed)
                    detect_key_literals(sf, state, opts, claimed)
                for predicate, detector in DETECTORS:
                    if predicate(sf):
                        detector(sf, state, opts)
                state.files_scanned += 1
            except Exception:
                state.stats["files_errored"] += 1
                state.partial = True
            finally:
                sf = None
                text = None
                data = None
    return state


# ----------------------------------------------------------------- resolver

def _q(answer, confidence, evidence):
    return {"answer": answer, "confidence": confidence, "evidence": list(evidence)}


def resolve(state):
    ev = state.evidence
    ef = state.effects
    out = {}

    def summary(key):
        if not ev[key]:
            return [{"path": "", "line": 0, "snippet": "%d files scanned, 0 hits" % state.files_scanned, "check": "scan-summary"}]
        return ev[key]

    for key in ("q1", "q3"):
        if "no" in ef[key]:
            out[key] = _q("no", "high", ev[key])
        else:
            out[key] = _q("dont-know", "med", summary(key))
    for key in ("q2", "q8", "q9"):
        out[key] = _q("dont-know", "med" if ev[key] else "low", ev[key])
    for key in ("q4", "q7", "q10", "q11"):
        out[key] = _q("dont-know", "low", ev[key])
    code_ev = ev["q5.code"]
    if state.git["commits"] is None:
        code = _q("dont-know", "low", code_ev)
    elif state.git["shallow"]:
        code = _q("dont-know", "med", code_ev)
    elif "git-subdir" in [e["check"] for e in code_ev]:
        code = _q("dont-know", "med", code_ev)
    elif (state.git["tags"] >= 1 or state.git["commits"] >= 10) and state.deploy_configs:
        code = _q("yes", "med", code_ev)
    else:
        code = _q("dont-know", "med", code_ev)
    out["q5"] = {"code": code, "data": _q("dont-know", "low", ev["q5.data"])}
    if len(state.env_names) >= 2:
        out["q6"] = _q("yes", "med", ev["q6"])
    else:
        out["q6"] = _q("dont-know", "med" if ev["q6"] else "low", ev["q6"])
    ordered = {}
    for i in range(1, 12):
        ordered["q%d" % i] = out["q%d" % i]
    return ordered


def scan(repo, **kwargs):
    opts = Options(**kwargs)
    state = ScanState()
    run_scan(repo, state, opts)
    return build_result(state, repo)


def build_result(state, repo):
    try:
        if os.path.realpath(repo) == os.path.realpath(os.getcwd()):
            state.warnings.append("repo-is-cwd")
    except OSError:
        pass
    return {
        "ok": True,
        "partial": bool(state.partial),
        "version": __version__,
        "files_scanned": state.files_scanned,
        "stats": state.stats,
        "warnings": list(state.warnings),
        "git": state.git,
        "questions": resolve(state),
    }


# ---------------------------------------------------------------------- CLI

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def envelope(code):
    base = code.split(":", 1)[0]
    hint, docs = HINTS.get(base, HINTS["internal"])
    return {"ok": False, "error": code, "hint": hint, "docs": docs, "partial": True}


def emit(obj, pretty=False):
    if pretty:
        sys.stdout.write(json.dumps(obj, ensure_ascii=True, indent=2) + "\n")
    else:
        sys.stdout.write(json.dumps(obj, ensure_ascii=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _Parser(prog="custody_scan.py", add_help=True, description="Read-only evidence gatherer for the eleven custody questions.")
    parser.add_argument("--repo", help="the app folder (run from the folder that contains it)")
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--max-file-bytes", type=int, default=524288)
    parser.add_argument("--max-total-bytes", type=int, default=268435456)
    parser.add_argument("--deadline-s", type=float, default=120.0)
    parser.add_argument("--exclude-dir", action="append", default=[])
    parser.add_argument("--browser-prefix", action="append", default=[])
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--exit-code", action="store_true")
    parser.add_argument("--version", action="store_true")
    started = time.monotonic()
    pretty = "--pretty" in argv
    exit_code = "--exit-code" in argv
    try:
        args = parser.parse_args(argv)
        if args.version:
            sys.stdout.write(__version__ + "\n")
            return 0
        if not args.repo:
            sys.stderr.write("Missing --repo. Try: python3 custody_scan.py --repo my-app\n")
            raise UsageError("--repo is required")
        repo = os.path.realpath(os.path.expanduser(args.repo.rstrip("/") or "/"))
        if not os.path.exists(repo):
            emit(envelope("repo-not-found"), pretty)
            return 2 if exit_code else 0
        if not os.path.isdir(repo):
            emit(envelope("repo-not-a-directory"), pretty)
            return 2 if exit_code else 0
        if not os.access(repo, os.R_OK | os.X_OK):
            emit(envelope("repo-unreadable"), pretty)
            return 2 if exit_code else 0
        opts = Options(max_files=args.max_files, max_file_bytes=args.max_file_bytes, max_total_bytes=args.max_total_bytes,
                       deadline_s=args.deadline_s, exclude_dirs=args.exclude_dir, browser_prefixes=args.browser_prefix)
        state = ScanState()
        run_scan(repo, state, opts)
        result = build_result(state, repo)
        emit(result, pretty)
        skipped = sum(state.stats[k] for k in ("files_skipped_oversize", "files_skipped_binary", "files_skipped_generated", "files_never_open", "files_skipped_special"))
        sys.stderr.write("custody-check v%s: scanned %d, skipped %d, errored %d, %d ms\n" % (
            __version__, state.files_scanned, skipped, state.stats["files_errored"], int((time.monotonic() - started) * 1000)))
        return 3 if (exit_code and result["partial"]) else 0
    except UsageError:
        emit(envelope("usage"), pretty)
        return 2 if exit_code else 0
    except SystemExit:
        raise
    except Exception as exc:  # last resort: never a traceback, never a path
        emit(envelope("internal:" + type(exc).__name__), pretty)
        return 2 if exit_code else 0


if __name__ == "__main__":
    sys.exit(main())
