#!/usr/bin/env python3
"""custody_scan.py: read-only evidence gatherer for the eleven custody questions.

Runs on python 3.9+ with the standard library only. Reads a repository (never
its instruction files), never writes, never talks to the network, and prints one
JSON line whose strings have all been through a redaction sweep. Exit code 0
always, unless --exit-code is given.

Run it from the folder that CONTAINS the app:  python3 -I custody_scan.py --repo ./my-app
"""
import sys

__version__ = "0.3.0"

_DOCS = "README.md#when-it-goes-wrong"
HINTS = {
    "usage": ("Pass the app folder with --repo. Run from the folder that contains your app: python3 custody_scan.py --repo my-app", _DOCS),
    "repo-not-found": ("The --repo folder was not found. Run from the folder that contains your app and pass its name.", _DOCS),
    "repo-not-a-directory": ("The --repo path is a file, not a folder. Pass the app folder itself.", _DOCS),
    "repo-is-symlink": ("The --repo path is a symbolic link. Pass the real folder (the link's target) instead.", _DOCS),
    "repo-unreadable": ("The --repo folder cannot be read. Check its permissions or copy the app somewhere you own.", _DOCS),
    "python-too-old": ("This scanner needs python 3.9 or newer. Run python3 --version; on macOS install the Command Line Tools, on Windows use py -3.", _DOCS),
    "repo-contains-cwd": ("The folder you named contains the folder you launched from. Run from the folder that contains your app and pass its name, never .. or a parent.", _DOCS),
    "internal": ("The scanner hit an unexpected error. Answer the eleven questions by hand and file an issue with the error code.", _DOCS),
}


def version_guard(version_info):
    """Return a failure envelope when the interpreter is too old, else None."""
    if tuple(version_info[:2]) < (3, 9):
        hint, docs = HINTS["python-too-old"]
        return {"ok": False, "error": "python-too-old", "hint": hint, "docs": docs, "partial": True}
    return None


_guard = version_guard(sys.version_info)
if _guard is not None and __name__ == "__main__":
    import json as _json
    sys.stdout.write(_json.dumps(_guard, separators=(",", ":")) + "\n")
    sys.exit(0)

import argparse
import base64
import bisect
import json
import os
import re
import select
import signal
import threading
import stat
import subprocess
import time
import unicodedata
import warnings


# ----------------------------------------------------------------- constants

BUILD_OUTPUT_DIRS = {"dist", "build", "out"}  # skipped like the rest, but people also keep source under these names
EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "vendor", "venv", ".venv", "__pycache__", "coverage"}
NEVER_OPEN_DIRS = {".claude", ".codex", ".agents", ".windsurf", ".clinerules", ".gemini", ".kiro", ".roo", ".trae", ".augment", ".amazonq", ".junie", ".continue", ".aider", ".opencode"}
NEVER_OPEN_DIR_PAIRS = {(".cursor", "rules"), (".github", "instructions"), (".github", "prompts"), (".github", "agents")}
NEVER_OPEN_FILE_RE = re.compile(r"^(?:claude|agents?|gemini|conventions|copilot-instructions)(?:[.-][^/]*)?\.md$|^\.aider.*$|.*\.prompt\.md$|.*\.agent\.md$|.*\.instructions\.md$|.*\.mdc$", re.I)
NEVER_OPEN_FILES = {".cursorrules", ".windsurfrules", ".clinerules", ".rules", "opencode.json", ".roomodes"}
SKIP_BASENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "poetry.lock", "cargo.lock", "composer.lock", "gemfile.lock"}
SKIP_EXT_SUFFIXES = (".map", ".min.js", ".min.css", ".bundle.js")
BROWSER_PREFIXES = ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "EXPO_PUBLIC_", "PUBLIC_", "NUXT_PUBLIC_", "GATSBY_")
ENV_TEMPLATE_NAMES = {".env.example", ".env.sample", ".env.template"}
ENV_TEMPLATE_RE = re.compile(r"(?:^|[._-])(?:example|sample|template|dist|defaults)(?:$|[._-])", re.I)
CLIENT_TOP_DIRS = {"src", "app", "pages", "components", "public", "static"}
NEUTRAL_SEGMENTS = {"lib", "utils", "services", "db", "scripts", "workers", "jobs", "cron"}
SERVER_FILE_RE = re.compile(r"^middleware\.[^/]+$|\.server\.[^./]+$|^route\.[jt]s$|^\+server\.[jt]s$")
DEPLOY_CONFIG_BASENAMES = {"vercel.json", "netlify.toml", "fly.toml", "render.yaml", "render.yml", "railway.json", "dockerfile", "procfile"}
IGNORED_ENV_NAMES = {"development", "dev", "local", "test", "testing", "default", "example", "sample", "template"}
NONPROD_ENV_STEMS = (IGNORED_ENV_NAMES - {"local"}) | {"ci", "vault", "enc", "sops", "age"}  # .env.local holds the real secrets  # tracked on purpose in most scaffolds
SOURCE_ROOTS = {"src", "app", "pages", "api", "server", "supabase", "prisma", "functions", "lib", "components", "netlify", "workers"}
_HAS_NONBLOCK = hasattr(os, "set_blocking") and sys.platform != "win32"
CONFIG_VALUE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
SQL_LIKE_EXTS = {".sql", ".psql", ".pgsql", ".ddl"}
CODE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".py", ".rb", ".go", ".java", ".kt", ".php", ".cs", ".swift", ".dart"}
SCHEMA_EXTS = {".prisma", ".graphql", ".gql"}
HTML_EXTS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro"}
MAX_EVIDENCE = 12
MAX_SNIPPET = 120
MAX_HITS_PER_FILE_PER_CHECK = 5
MAX_PATH_CHARS = 200
BINARY_SNIFF_BYTES = 8192
MCP_MAX_CHARS = 65536
MCP_MAX_DEPTH = 64
MCP_MAX_NODES = 10000
LINE_CLIP_CHARS = 2048
MAX_SEEN = 20000
GIT_BUDGET_S = 15.0
MAX_NEVER_OPEN_COUNT = 10000
MAX_TRACKED_ENV_FILES = MAX_EVIDENCE
DEFAULT_MAX_FILES = 20000
DEFAULT_MAX_FILE_BYTES = 524288
DEFAULT_MAX_TOTAL_BYTES = 268435456
DEFAULT_DEADLINE_S = 120.0
ENV_FILE_RE = re.compile(r"^\.env([._-].+)?$")
FLY_ENV_TOML_RE = re.compile(r"^fly\.([a-z0-9_-]+)\.toml$")
DEADLINE_TICK = 256
MAX_JWT_HITS_PER_FILE = 200
MAX_ENV_NAME_MATCHES = 200
MAX_DIR_ENTRIES = 50000
GIT_OUTPUT_LIMIT = 1 << 20
MAX_CONFIG_ENTRIES = 20
MAX_CONFIG_CHARS = 64
MAX_OUTPUT_BYTES = 30000  # under the host's tool-output window, so the line is never truncated on the way to the agent
STOPLINE_FIELDS = {"ssn", "social_security", "dob", "date_of_birth", "birthdate", "medical", "diagnosis", "credit_card", "card_number", "cc_number", "iban", "passport"}
RUN_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-+/=.")
ENV_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# effects: evidence < hint < yes-part < no
CHECKS = {
    "tracked-env-file": ("q1", "no"), "tracked-env-file-nonprod": ("q1", "evidence"), "env-file-on-disk": ("q1", "evidence"),
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
    "nothing-found-keys": ("q1", "evidence"), "build-output-unread": ("q1", "evidence"),
    "api-route-dir": ("q2", "hint"), "framework-config": ("q2", "hint"), "client-server-split": ("q2", "hint"),
    "rls-disabled": ("q3", "no"), "policy-using-true": ("q3", "no"), "policy-select-true": ("q3", "evidence"), "policy-altered-true": ("q3", "evidence"), "policy-with-check-true": ("q3", "evidence"),
    "policy-to-anon": ("q3", "evidence"), "table-without-rls": ("q3", "evidence"), "storage-bucket-public-sql": ("q3", "evidence"), "nothing-found-rules": ("q3", "evidence"),
    "firebase-rules-open": ("q3", "no"), "firebase-rules-public-read": ("q3", "evidence"), "storage-bucket-public": ("q3", "evidence"),
    "auth-path": ("q4", "evidence"), "auth-dependency": ("q4", "evidence"),
    "deploy-config": ("q5.code", "yes-part"), "migration-path": ("q5.code", "evidence"), "backup-script": ("q5.code", "evidence"),
    "git-history": ("q5.code", "evidence"), "git-not-a-repo": ("q5.code", "evidence"), "git-config-not-vouched": ("q5.code", "evidence"), "git-index-unread": ("q1", "evidence"), "git-unavailable": ("q5.code", "evidence"),
    "git-timeout": ("q5.code", "evidence"), "git-subdir": ("q5.code", "evidence"), "git-shallow": ("q5.code", "evidence"),
    "env-name": ("q6", "yes-part"), "preview-deploys-default": ("q6", "evidence"),
    "review-workflow": ("q7", "evidence"),
    "model-env-var": ("q8", "hint"), "model-literal": ("q8", "hint"), "spend-cap-word": ("q8", "hint"), "ai-sdk-dependency": ("q8", "hint"),
    "monitoring-dependency": ("q9", "hint"), "sentry-config": ("q9", "hint"), "health-route": ("q9", "hint"), "cron-schedule": ("q9", "hint"), "nothing-found-monitoring": ("q9", "evidence"),
    "pii-field": ("q10", "evidence"), "pii-form-input": ("q10", "evidence"),
    "builder-file": ("q11", "evidence"), "builder-dependency": ("q11", "evidence"), "builder-readme": ("q11", "evidence"), "container-config": ("q11", "evidence"), "code-history-local": ("q11", "evidence"),
}
QUESTION_KEYS = ["q1", "q2", "q3", "q4", "q5.code", "q5.data", "q6", "q7", "q8", "q9", "q10", "q11"]
for _name, (_q, _e) in CHECKS.items():
    assert _q in QUESTION_KEYS and _e in ("evidence", "hint", "yes-part", "no"), _name

# ------------------------------------------------------------------ regexes

NAMED_KEY_ALT = r"sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sb_secret_[A-Za-z0-9_-]{10,}"
NAMED_KEY_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:" + NAMED_KEY_ALT + r")(?![A-Za-z0-9_-])")
NAMED_KEY_FULL_RE = re.compile(r"(?:" + NAMED_KEY_ALT + r")")
JWT_RE = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])")
JWT_RUN_RE = re.compile(r"[A-Za-z0-9_.-]{27,}")
JWT_SEG_RE = re.compile(r"[A-Za-z0-9_-]{8,}")
RUN_RE = re.compile(r"[A-Za-z0-9_\-+/=.]{20,}")
PUBLIC_KEY_RE = re.compile(r"sb_publishable_[A-Za-z0-9_-]+|pk_(?:live|test)_[A-Za-z0-9]+|AIza[0-9A-Za-z_-]{35}")
MAX_VALUE_CHARS = 8192
PUBLIC_PREFIX_RE = re.compile(r"^(?:sb_publishable_|pk_live_|pk_test_|AIza[0-9A-Za-z_-]{35})")
WORDY_NAME_RE = re.compile(r"^(?:[A-Z][A-Z0-9]*|[a-z][a-z0-9]*)(?:_(?:[A-Z][A-Z0-9]*|[a-z][a-z0-9]*)){1,15}$")
GENERIC_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-+/=]{32,}")
PLACEHOLDER_RE = re.compile(r"your|xxx+|placeholder|example|replace|changeme|dummy", re.I)
IDENT_SENSITIVE_RE = re.compile(r"secret|service[_-]?(?:role|key|token)", re.I)
IDENT_BEFORE_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)[ \t]*[:=][ \t]*[\"'`]?[ \t]*$")
IDENT_KEYISH_RE = re.compile(r"key|token", re.I)
IDENT_ASSIGN_TOKEN_RE = re.compile(r"\b(?P<ident>[A-Za-z_][A-Za-z0-9_]*)[\"']?[ \t]*[:=][ \t]*[\"'`]?(?P<value>[A-Za-z0-9_\-+/=.]{32,})")
USE_CLIENT_RE = re.compile(r"^[ \t]*[\"']use client[\"']", re.M)
CLIENT_IMPORT_RE = re.compile(r"(?m)^[ \t]*import\b[^\n]{0,200}\bfrom[ \t]+[\"'](?:react|react-dom|vue|svelte|next|@sveltejs/kit|@angular/[a-z-]{1,40})(?:/[^\"'\n]{0,80})?[\"']|require\([\"'](?:react|vue|svelte|next)[\"']\)")
SERVER_ONLY_IMPORT_RE = re.compile(r"(?m)^[ \t]*import\b[^\n]{0,200}[\"'](?:next/(?:headers|server|cache)|server-only)[\"']")
ANGULAR_IMPORT_RE = re.compile(r"(?m)^[ \t]*import\b[^\n]{0,200}\bfrom[ \t]+[\"']@angular/")
PAGES_DATA_FN_RE = re.compile(r"\b(?:getServerSideProps|getStaticProps|getStaticPaths)\b")
TEST_PATH_RE = re.compile(r"(?:^|/)(?:__tests__|tests?|fixtures?)/|\.(?:test|spec|stories)\.[^/]+$")
RLS_DISABLED_RE = re.compile(r"disable\s{1,20}row\s{1,20}level\s{1,20}security", re.I)
USING_TRUE_RE = re.compile(r"\busing\s{0,20}\((?:\s{0,20}\(){0,3}\s{0,20}true(?:\s{0,5}::\s{0,5}bool(?:ean)?)?(?:\s{0,20}\)){1,4}", re.I)
WITH_CHECK_TRUE_RE = re.compile(r"\bwith\s{1,20}check\s{0,20}\(\s{0,20}true\s{0,20}\)", re.I)
POLICY_TO_ANON_RE = re.compile(r"\bcreate\s+policy\b[^\n]{0,300}?\bto\s+anon\b", re.I)
STORAGE_BUCKET_TRUE_RE = re.compile(r"storage\.buckets\b[^\n]{0,300}?\btrue\b", re.I)
FIREBASE_ALLOW_ALL_RE = re.compile(r"\ballow[ \t]{1,20}([a-z]+(?:[ \t]*,[ \t]*[a-z]+){0,10})[ \t]*;", re.I)
FIREBASE_ALLOW_TRUE_RE = re.compile(r"\ballow[ \t]{1,20}([a-z]+(?:[ \t]*,[ \t]*[a-z]+){0,10})[ \t]*:[ \t]*if[ \t]{1,20}true\b", re.I)
FIREBASE_WRITE_RE = re.compile(r"\b(?:write|create|update|delete)\b", re.I)
RTDB_WRITE_OPEN_RE = re.compile(r"\"\.write\"\s{0,20}:\s{0,20}true", re.I)
RTDB_READ_OPEN_RE = re.compile(r"\"\.read\"\s{0,20}:\s{0,20}true", re.I)
SLASH_COMMENT_RE = re.compile(r"//[^\n]*")
RN_IMPORT_RE = re.compile(r"(?m)^[ \t]*import\b[^\n]{0,200}\bfrom[ \t]+[\"'](?:react-native|expo|expo-router|@expo/[^\"'\n]{0,60})[\"']")
TOML_PUBLIC_TRUE_RE = re.compile(r"^[ \t]*public[ \t]*=[ \t]*true\b", re.I | re.M)
NETLIFY_CONTEXT_RE = re.compile(r"^[ \t]*\[context\.([A-Za-z0-9_-]{1,32})(?:\.[^\]\n]{0,80})?\]", re.M)
WRANGLER_ENV_RE = re.compile(r"^[ \t]*\[env\.([A-Za-z0-9_-]{1,32})(?:\.[^\]\n]{0,80})?\]", re.M)
VERCEL_ENV_RE = re.compile(r"\"(production|preview|staging)\"\s*:")
MODEL_PROVIDER_ALT = "OPENAI|ANTHROPIC|CLAUDE|GEMINI|GOOGLE_AI|GOOGLE_GENERATIVE_AI|MISTRAL|COHERE|GROQ|TOGETHER|REPLICATE|HUGGINGFACE|AZURE_OPENAI|OPENROUTER|XAI|DEEPSEEK|PERPLEXITY|FIREWORKS"
MODEL_PROVIDER_RE = re.compile(r"(?:" + MODEL_PROVIDER_ALT + r")_", re.I)
MODEL_ENV_RE = re.compile(r"\b((?:" + MODEL_PROVIDER_ALT + r"|HF)_[A-Z0-9_]*(?:KEY|TOKEN|SECRET))\b")  # HF_ is too short to trust as a provider prefix on a Google key
MODEL_LITERAL_RE = re.compile(r"(?<![A-Za-z0-9])(?:gpt-[0-9][A-Za-z0-9.-]*|claude-[a-z0-9.-]+|gemini-[a-z0-9.-]+|llama[-_]?[0-9][A-Za-z0-9.-]*|mistral-[a-z0-9.-]+|o[134]-mini|o3)(?![A-Za-z0-9])")
SPEND_CAP_RE = re.compile(r"\b(?:max_tokens|maxTokens|rate_limit|rateLimit|spend_cap|budget_limit|maxDuration)\b")
HEALTH_ROUTE_RE = re.compile(r"[\"'`]/(?:api/)?health(?:z|check|-check)?[\"'`]")
CRON_VERCEL_RE = re.compile(r"\"crons\"\s*:")
CRON_WORKFLOW_RE = re.compile(r"^[ \t]*(?:-[ \t]*)?cron[ \t]*:", re.M)
CRON_WRANGLER_RE = re.compile(r"^[ \t]*crons[ \t]*=", re.M)
CRON_SQL_RE = re.compile(r"cron\.schedule\(", re.I)
PII_FIELD_RE = re.compile(r"(?<![a-z0-9])(email|phone|tel|ssn|social_security|dob|date_of_birth|birthdate|address|street|postal_code|zip_code|passport|credit_card|card_number|cc_number|iban|medical|diagnosis|salary)(?![a-z0-9])", re.I)
CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
POLICY_SELECT_RE = re.compile(r"\bfor\s{1,20}select\b", re.I)
PII_INPUT_RE = re.compile(r"name=[\"'](email|tel|phone|address|street|cc-[a-z-]+|bday|ssn|dob)[\"']", re.I)
BUILDER_URL_RE = re.compile(r"lovable\.(?:dev|app)|replit\.com|bolt\.new|base44\.com|v0\.(?:dev|app)", re.I)
DEP_NAME_RE = re.compile(r"\"(@?[A-Za-z0-9_./-]+)\"\s*:")
_prefix_alt = "|".join(re.escape(p) for p in BROWSER_PREFIXES)
PREFILTER_RE = re.compile(NAMED_KEY_ALT + r"|eyJ[A-Za-z0-9_-]{8,}|(?:[Ss]ecret|SECRET|[Ss]ervice|SERVICE|[Kk]ey|KEY|[Tt]oken|TOKEN)[A-Za-z0-9_]{0,64}[\"']?[ \t]*[:=]|" + _prefix_alt)

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
REVIEW_ACTION_RE = re.compile(r"^[ \t]*(?:-[ \t]*)?uses:[ \t]*[\"']?(anthropics/claude-code-action|coderabbitai/[A-Za-z0-9_.-]{1,60}|reviewdog/[A-Za-z0-9_.-]{1,60})", re.M)
REVIEW_NAME_RE = re.compile(r"(?:^|[-_.])review")  # pr-review.yml, claude-code-review.yml; never preview.yml
CREATE_TABLE_RE = re.compile(r"\bcreate\s{1,20}table\s{1,20}(?:if\s{1,20}not\s{1,20}exists\s{1,20})?(" + r"(?:\"[^\"\n]{1,63}\"|[A-Za-z_][A-Za-z0-9_$]{0,62})(?:\s{0,5}\.\s{0,5}(?:\"[^\"\n]{1,63}\"|[A-Za-z_][A-Za-z0-9_$]{0,62}))?)", re.I)
ENABLE_RLS_RE = re.compile(r"\balter\s{1,20}table\s{1,20}(?:if\s{1,20}exists\s{1,20})?(?:only\s{1,20})?(" + r"(?:\"[^\"\n]{1,63}\"|[A-Za-z_][A-Za-z0-9_$]{0,62})(?:\s{0,5}\.\s{0,5}(?:\"[^\"\n]{1,63}\"|[A-Za-z_][A-Za-z0-9_$]{0,62}))?)\s{1,20}enable\s{1,20}row\s{1,20}level\s{1,20}security", re.I)
MANIFEST_BASENAMES = {"package.json", "requirements.txt", "pyproject.toml", "gemfile", "go.mod"}
GENERATED_CODE_SUFFIXES = (".min.js", ".bundle.js", ".map")  # browser code, or source maps that embed it
PREVIEW_DEFAULTS = {"vercel.json": "Vercel previews every branch by default", "netlify.toml": "Netlify deploy previews on by default"}
# every extension a Q1 or Q3 detector reads; an oversize file of any other kind (a photo, a font, a video)
# cannot hide a key or an open rule, so skipping it leaves the scan complete
Q1_Q3_EXTS = CODE_EXTS | HTML_EXTS | SQL_LIKE_EXTS | {".json", ".toml", ".yml", ".yaml"}


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
    if len(piece) < 32 or not GENERIC_TOKEN_RE.fullmatch(piece):
        return piece
    if "/" in piece and "+" not in piece and "=" not in piece:
        # an ordinary slash-separated path is not a token; base64 with "/" also carries "+" or "="
        # and mixes lower, upper and digits, which a path rarely does
        alpha_classes = sum(1 for test in (str.islower, str.isupper, str.isdigit) if any(test(c) for c in piece))
        return redact_value(piece) if alpha_classes >= 3 else piece
    if WORDY_NAME_RE.match(piece):
        return piece  # an ordinary variable or path name (NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY), not a value
    if _classes(piece) >= 2:
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
    if any(o != p for o, p in zip(out, pieces)) or len(out) != len(pieces):
        # a dotted token (SendGrid, JWT-like): once any piece is a secret, its siblings are too
        out = [redact_value(o) if (o == p and len(o) >= 16 and re.fullmatch(r"[A-Za-z0-9_\-+/=]+", o)) else o for o, p in zip(out, pieces)]
    return ".".join(out)


def _mask_quoted(text):
    """Hide every quoted string (other than the matched value) on a hit line: passwords are rarely token-shaped.

    A linear scan, so a quoted string of any length is masked up to its closing quote or the end of the text.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            j = text.find(c, i + 1)
            if j < 0:
                # an unmatched quote: the matched value's own opener when it is the last character, otherwise
                # an unterminated string whose remainder is masked to the end (it may hold a password)
                out.append(c if i == n - 1 else c + "\u2026")
                break
            out.append(c + "\u2026" + c)
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def sweep(text):
    """Linear-time redaction: JWT triples first (narrow charset, so glued query strings still split), then every token run piece by piece."""
    spans = list(find_jwts(text))
    if spans:
        out = []
        pos = 0
        for start, end in spans:
            out.append(text[pos:start])
            out.append(redact_value(text[start:end]))
            pos = end
        out.append(text[pos:])
        text = "".join(out)
    return RUN_RE.sub(_redact_run, text)


def find_jwts(text):
    """Yield (start, end) of every JWT-shaped triple, linear in the text length."""
    for m in JWT_RUN_RE.finditer(text):
        run = m.group(0)
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


def _drop_format_chars(text):
    """Bidi overrides, zero-width and other format characters can reorder rendered text; drop them."""
    return "".join(c for c in text if not (unicodedata.category(c) in ("Cf", "Cc") or c in "\u2028\u2029"))


def sanitize(text, limit=MAX_SNIPPET):
    text = str(text).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = _drop_format_chars(CONTROL_RE.sub("", text))
    text = sweep(text)
    if len(text) > limit:
        text = text[:limit]
    return text


def sanitize_path(rel):
    """Redact segment by segment so a nested path stays readable while a secret-shaped name is still hidden."""
    rel = rel.replace(os.sep, "/")
    cleaned = "/".join(sanitize(seg, MAX_PATH_CHARS) for seg in rel.split("/"))
    return cleaned[:MAX_PATH_CHARS]


def make_snippet(text, start, end):
    """Clip to the matched line, redact the WHOLE line first, then window around the match.

    Sweeping before windowing matters: a window cut through a neighbouring secret would
    leave a fragment too short for any pattern to catch.
    """
    line_start = _line_start(text, start)
    hi = min(len(text), end + 2048)
    le = text.find("\n", end, hi)
    line_end = le if le >= 0 else hi
    steps = 0
    while line_start > 0 and text[line_start - 1] in RUN_CHARS and steps < 8192:
        line_start -= 1
        steps += 1
    steps = 0
    while line_end < len(text) and text[line_end] in RUN_CHARS and steps < 8192:
        line_end += 1
        steps += 1
    before = _mask_quoted(sweep(text[line_start:start]))
    value = sweep(text[start:end])
    tail = sweep(text[end:line_end])
    quote = before[-1] if before and before[-1] in "\"'`" else None
    if quote and tail.startswith(quote):
        tail = quote + _mask_quoted(tail[1:])
    else:
        tail = _mask_quoted(tail)
    after = value + tail
    line = before + after
    s = len(before)
    if len(line) > MAX_SNIPPET:
        left = max(0, s - 40)
        line = line[left:left + MAX_SNIPPET]
    return sanitize(line)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def _line_start(text, pos):
    """Start of the line holding pos, never more than LINE_CLIP_CHARS back (a huge single line stays bounded)."""
    lo = max(0, pos - LINE_CLIP_CHARS)
    ls = text.rfind("\n", lo, pos)
    return ls + 1 if ls >= 0 else lo


def is_generic_token(value, min_classes=3):
    if len(value) < 32 or len(value) > MAX_VALUE_CHARS or not GENERIC_TOKEN_RE.fullmatch(value.rstrip(".")):
        return False
    classes = _classes(value)
    if classes >= 3:
        return True
    return min_classes <= 2 and classes >= 2 and any(c.isdigit() for c in value)  # hex secrets under a sensitive name


def is_placeholder(value, is_jwt):
    if PLACEHOLDER_RE.search(value):
        return True
    if value.startswith("sk-") and value.count("-") > 5:
        return True  # a hyphenated slug (a CSS class such as sk-fading-circle-container), not a key
    if NAMED_KEY_FULL_RE.match(value) and not value.startswith("sk-"):
        return False  # a real key shape wins over the digit heuristic (AWS ids are base32 and can lack digits)
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
    def __init__(self, max_files=DEFAULT_MAX_FILES, max_file_bytes=DEFAULT_MAX_FILE_BYTES, max_total_bytes=DEFAULT_MAX_TOTAL_BYTES, deadline_s=DEFAULT_DEADLINE_S, exclude_dirs=(), browser_prefixes=()):
        self.max_files = int(max_files)
        self.max_file_bytes = int(max_file_bytes)
        self.max_total_bytes = int(max_total_bytes)
        self.deadline_s = float(deadline_s)
        self.exclude_dirs_added = []
        for d in exclude_dirs:
            d = str(d).strip().strip("/").lower()
            # over-length or path-like values are dropped, never shortened into a different name
            if not d or len(d) > MAX_CONFIG_CHARS or d == "." or "/" in d or d in NEVER_OPEN_DIRS or d in EXCLUDED_DIRS or not CONFIG_VALUE_RE.match(d):
                continue
            if d not in self.exclude_dirs_added and len(self.exclude_dirs_added) < MAX_CONFIG_ENTRIES:
                self.exclude_dirs_added.append(d)
        self.browser_prefixes_added = []
        for p in browser_prefixes:
            p = str(p).strip()
            if not re.fullmatch(r"[A-Za-z0-9_]{1,%d}" % MAX_CONFIG_CHARS, p):
                continue
            if p not in BROWSER_PREFIXES and p not in self.browser_prefixes_added and len(self.browser_prefixes_added) < MAX_CONFIG_ENTRIES:
                self.browser_prefixes_added.append(p)
        self.excluded = EXCLUDED_DIRS | set(self.exclude_dirs_added)
        self.prefixes = tuple(BROWSER_PREFIXES) + tuple(self.browser_prefixes_added)
        alt = "|".join(re.escape(p) for p in self.prefixes)
        self.browser_assign_re = re.compile(r"[\"']?\b(?P<name>(?:" + alt + r")[A-Za-z0-9_]+)[\"']?\s*[=:]\s*[\"'`]?(?:[A-Za-z][A-Za-z-]{1,20}[ \t]+)?(?P<value>[A-Za-z0-9_\-+/=.]{16,})")
        self.prefilter_re = re.compile(PREFILTER_RE.pattern + ("|" + alt if self.browser_prefixes_added else ""))


class ScanFile(object):
    __slots__ = ("rel", "base", "ext", "cls", "kinds", "text")

    def __init__(self, rel, base, ext, cls, kinds, text):
        self.rel = rel
        self.base = base
        self.ext = ext
        self.cls = cls
        self.kinds = kinds
        self.text = text


class Deadline(Exception):
    """Raised inside a file's detectors when the global deadline passes."""


def _empty_git():
    return {"commits": None, "tags": None, "shallow": None, "tracked_env_files": None}


class ScanState(object):
    def __init__(self):
        self.files_scanned = 0
        self.partial = False
        self.git = _empty_git()
        self.deadline = None
        self.ticks = 0
        self.evidence = dict((k, []) for k in QUESTION_KEYS)
        self.effects = dict((k, set()) for k in QUESTION_KEYS)
        self.env_names = set()
        self.deploy_configs = []
        self.cls_counts = {"client": 0, "server": 0, "other": 0}
        self.q1_files = 0
        self.rule_files = 0
        self.manifests = 0
        self.dependencies = 0
        self.gaps = {"q1": 0, "q3": 0, "q9": 0}  # files that could answer the question and were not read
        self.tables = {}  # public table name -> (path, line) of its create table
        self.rls_enabled = set()
        self.seen = set()
        self.warnings = []
        self.stats = {"files_skipped_oversize": 0, "files_skipped_oversize_relevant": 0, "files_skipped_binary": 0, "files_skipped_generated": 0, "files_never_open": 0,
                      "files_skipped_special": 0, "files_skipped_hardlink": 0, "files_errored": 0, "dirs_unreadable": 0, "dirs_truncated": 0, "mcp_capped": 0, "git_index_partial": 0, "output_trimmed": 0, "max_files_hit": False,
                      "max_total_bytes_hit": False, "deadline_hit": False, "config": {"exclude_dirs_added": [], "browser_prefixes_added": []}}

    def tick(self):
        """Cheap mid-file deadline check; called from hit loops."""
        self.ticks += 1
        if self.deadline is not None and self.ticks % DEADLINE_TICK == 0 and time.monotonic() > self.deadline:
            raise Deadline()

    def add(self, check, path, line, snippet):
        question, effect = CHECKS[check]
        self.effects[question].add(effect)
        key = (check, path, line, snippet)
        if key in self.seen:
            return
        if len(self.seen) < MAX_SEEN:
            self.seen.add(key)
        row = {"path": sanitize_path(path), "line": int(line), "snippet": sanitize(snippet), "check": check}
        rows = self.evidence[question]
        if len(rows) < MAX_EVIDENCE:
            rows.append(row)
        elif effect == "no":
            # a row that decides the answer must never be crowded out by evidence-only rows
            for i in range(len(rows) - 1, -1, -1):
                if CHECKS[rows[i]["check"]][1] != "no":
                    del rows[i]
                    rows.append(row)
                    break


def iter_questions(result):
    for key, value in result["questions"].items():
        if key == "q5":
            yield value["code"]
            yield value["data"]
        else:
            yield value


# ---------------------------------------------------------------- filesystem

def is_env_file(base):
    """One definition of an env file: `.env`, `.env.<name>`, `<name>.env`, `.envrc`; templates are not env files."""
    b = base.lower()
    return (bool(ENV_FILE_RE.match(b)) or b.endswith(".env") or b == ".envrc") and not is_env_template(b)


def is_env_template(base):
    b = base.lower()
    return b in ENV_TEMPLATE_NAMES or bool(ENV_TEMPLATE_RE.search(b))


def is_never_open_dir(name, parent):
    n = name.lower()
    return n in NEVER_OPEN_DIRS or (parent.lower(), n) in NEVER_OPEN_DIR_PAIRS


def is_never_open_file(base):
    b = base.lower()
    return b in NEVER_OPEN_FILES or bool(NEVER_OPEN_FILE_RE.match(b))


def could_hold_q1_q3(base, ext):
    """A file a Q1 or Q3 detector would have read. Only skipping one of these leaves the scan incomplete."""
    b = base.lower()
    env_shaped = b.startswith(".env") or b.endswith(".env")  # the template word list alone matches `hero-sample.png`
    return ext in Q1_Q3_EXTS or is_env_file(b) or (env_shaped and is_env_template(b)) or b.endswith(".rules")


def note_unread(state, base, ext):
    """A file skipped for any reason: "nothing found" is off for every question it could have answered."""
    if could_hold_q1_q3(base, ext):
        state.gaps["q1"] += 1
        state.gaps["q3"] += 1
    if base.lower() in MANIFEST_BASENAMES:
        state.gaps["q9"] += 1


def note_unread_dir(state):
    for key in state.gaps:
        state.gaps[key] += 1


def skip_oversize(state, base, ext):
    state.stats["files_skipped_oversize"] += 1
    note_unread(state, base, ext)
    if could_hold_q1_q3(base, ext):
        state.stats["files_skipped_oversize_relevant"] += 1
        state.partial = True


def is_generated(base):
    b = base.lower()
    return b in SKIP_BASENAMES or b.endswith(SKIP_EXT_SUFFIXES)


def count_files(path, deadline=None):
    n = 0
    entries = 0
    for _, dirs, files in os.walk(path, followlinks=False, onerror=lambda e: None):
        n += len(files)
        entries += len(files) + len(dirs) + 1
        if n >= MAX_NEVER_OPEN_COUNT or entries >= MAX_NEVER_OPEN_COUNT or (deadline is not None and time.monotonic() > deadline):
            return min(n, MAX_NEVER_OPEN_COUNT)
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
    head = data[:BINARY_SNIFF_BYTES]
    if b"\x00" in head:
        half = len(head) // 2
        if half >= 8:
            odd = head[1::2].count(0)
            even = head[0::2].count(0)
            if odd >= half * 0.6 and even <= half * 0.05:
                return data.decode("utf-16-le", errors="replace")  # UTF-16 without a BOM (Windows editors)
            if even >= half * 0.6 and odd <= half * 0.05:
                return data.decode("utf-16-be", errors="replace")
        return None
    return data.decode("utf-8-sig", errors="replace")


def classify(rel, base, ext, text):
    segments = rel.split("/")
    dirs = segments[:-1]
    lower_dirs = [d.lower() for d in dirs]
    app_dirs = lower_dirs[1:] if lower_dirs and lower_dirs[0] == "src" else lower_dirs
    top = app_dirs[0] if app_dirs else ""
    kinds = set()
    b = base.lower()
    if is_env_file(b) or is_env_template(b):
        kinds.add("env-template" if is_env_template(b) else "env")
    if b in (".mcp.json", "mcp.json", "mcp_config.json"):
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
    cls = "other"
    # "api" is server code at the repository root (serverless functions) or under pages/app (Next);
    # src/api/ in a Vite or CRA app is usually the browser's fetch wrapper, so it stays client
    api_server = bool(lower_dirs) and (lower_dirs[0] in ("api", "server", "functions", "workers") or
                                       (bool(app_dirs) and app_dirs[0] in ("server", "functions", "workers")) or
                                       (len(app_dirs) >= 2 and app_dirs[0] in ("pages", "app", "netlify", "supabase") and app_dirs[1] in ("api", "functions")))
    if api_server or "server" in lower_dirs or SERVER_FILE_RE.search(base):
        cls = "server"
    elif ("env" in kinds or "env-template" in kinds) and top not in ("public", "static"):
        cls = "other"
    else:
        use_client = bool(USE_CLIENT_RE.search(text[:500]))
        client_import = bool(CLIENT_IMPORT_RE.search(text)) and not SERVER_ONLY_IMPORT_RE.search(text)
        native_import = bool(RN_IMPORT_RE.search(text))
        angular_import = bool(ANGULAR_IMPORT_RE.search(text))
        if any(d in NEUTRAL_SEGMENTS for d in lower_dirs):
            cls = "client" if (use_client or client_import or native_import) else "other"
        elif top == "app":
            cls = "client" if (use_client or native_import or angular_import) else "other"
        elif top == "pages":
            cls = "other" if PAGES_DATA_FN_RE.search(text) else "client"
        elif top in CLIENT_TOP_DIRS or (lower_dirs and lower_dirs[0] == "src") or ext in (".vue", ".svelte", ".html", ".htm") or use_client or client_import or native_import:
            cls = "client"
    return cls, kinds


# ---------------------------------------------------------------- detectors

def _cap(counter, check):
    counter[check] = counter.get(check, 0) + 1
    return counter[check] <= MAX_HITS_PER_FILE_PER_CHECK


def detect_browser_prefix(sf, state, opts, claimed):
    text = sf.text
    counter = {}
    is_env = "env" in sf.kinds or "env-template" in sf.kinds
    name_only = is_env or "yaml" in sf.kinds or "toml" in sf.kinds  # unquoted neighbours (passphrases) cannot be masked
    is_test = bool(TEST_PATH_RE.search(sf.rel))
    for m in opts.browser_assign_re.finditer(text):
        name, value = m.group("name"), _strip_scheme(m.group("value").rstrip("."))
        value_start = m.end("value") - len(value)
        if len(value) > MAX_VALUE_CHARS:
            state.gaps["q1"] += 1  # too long to judge: a browser-prefixed value the scanner did not look at
            continue  # not judged here, so its span stays open for the key-literal pass
        claimed.append((value_start, value_start + len(value)))
        named = bool(NAMED_KEY_FULL_RE.match(value))
        jwt = is_jwt(value)
        generic = is_generic_token(value)
        public = bool(PUBLIC_PREFIX_RE.match(value))
        if not (named or jwt or generic or public):
            continue
        state.tick()
        if is_placeholder(value, jwt):
            check = "placeholder-key-literal"
        elif is_test and (named or jwt or generic):
            check = "test-path-key-literal"
        elif IDENT_SENSITIVE_RE.search(name) and (named or jwt or generic):
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
            check = "browser-prefix-service-or-secret-name" if MODEL_PROVIDER_RE.search(name) else "browser-prefix-public-key"  # a Google key named for an AI provider is billable, not a web config
        else:
            check = "browser-prefix-token-shaped"
        if not _cap(counter, check):
            continue
        line = line_of(text, m.start())
        snippet = name if name_only else make_snippet(text, m.start(), m.end())
        state.add(check, sf.rel, line, snippet)


def detect_key_literals(sf, state, opts, claimed):
    text = sf.text
    counter = {}
    is_env = "env" in sf.kinds or "env-template" in sf.kinds
    name_only = is_env or "yaml" in sf.kinds or "toml" in sf.kinds  # unquoted neighbours (passphrases) cannot be masked
    is_test = bool(TEST_PATH_RE.search(sf.rel))

    starts = [c[0] for c in claimed]

    def overlaps(a, b):
        i = bisect.bisect_right(starts, a) - 1
        if i >= 0 and claimed[i][1] > a:
            return True
        if i + 1 < len(claimed) and claimed[i + 1][0] < b:
            return True
        return False

    hits = []
    for m in NAMED_KEY_RE.finditer(text):
        hits.append((m.start(), m.end(), "named", None))
    for start, end in find_jwts(text):
        hits.append((start, end, "jwt", None))
    for m in IDENT_ASSIGN_TOKEN_RE.finditer(text):
        value = m.group("value")
        if len(value) > MAX_VALUE_CHARS:
            if IDENT_SENSITIVE_RE.search(m.group("ident")) or IDENT_KEYISH_RE.search(m.group("ident")):
                state.gaps["q1"] += 1  # a key-shaped name over a value too long to judge; an image's base64 is not
            continue
        if NAMED_KEY_FULL_RE.match(value) or is_jwt(value):
            continue
        classes_needed = 2 if IDENT_SENSITIVE_RE.search(m.group("ident")) else 3  # a hex secret under apiSecret still counts
        if not is_generic_token(value.rstrip("."), classes_needed):
            continue
        hits.append((m.start("value"), m.end("value"), "generic", m.group("ident")))
    hits.sort(key=lambda h: (h[0], h[1]))
    jwt_seen = 0
    for start, end, kind, ident in hits:
        if overlaps(start, end):
            continue
        if kind == "jwt":
            jwt_seen += 1
            if jwt_seen > MAX_JWT_HITS_PER_FILE and counter.get("client-privileged-jwt", 0) >= MAX_HITS_PER_FILE_PER_CHECK \
                    and counter.get("client-secret-name-token", 0) >= MAX_HITS_PER_FILE_PER_CHECK:
                continue  # only once the decisive JWT checks are themselves capped is more decoding pointless
        state.tick()
        value = text[start:end]
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
            im = IDENT_BEFORE_RE.search(text[_line_start(text, start):start])
            if role == "service_role":
                check = "client-privileged-jwt"
            elif im and IDENT_SENSITIVE_RE.search(im.group(1)):
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
        if not check or not _cap(counter, check):
            continue
        line = line_of(text, start)
        if name_only:
            lstart = _line_start(text, start)
            snippet = re.split(r"[=:\s]", text[lstart:start].strip(), 1)[0][:60]
        else:
            snippet = make_snippet(text, start, end)
        state.add(check, sf.rel, line, snippet)


def _mcp_check_for(key):
    """A generic token under an auth-shaped key is decisive; under any other key it is evidence."""
    lk = key.lower()
    if IDENT_SENSITIVE_RE.search(key) or IDENT_KEYISH_RE.search(key) or lk in ("authorization", "password", "auth"):
        return "mcp-token"
    return "mcp-token-shaped"


def _strip_scheme(value):
    """`Bearer <token>` / `Basic <token>` / `token <token>`: judge the credential, not the header."""
    parts = value.split()
    if len(parts) == 2 and re.match(r"^[A-Za-z][A-Za-z-]{1,20}$", parts[0]):
        return parts[1]  # `Bearer <token>`, `ApiKey <token>`, `token <token>`: judge the credential
    return value


def detect_mcp(sf, state, opts):
    text = sf.text
    if len(text) > MCP_MAX_CHARS:
        state.stats["mcp_capped"] += 1
        state.gaps["q1"] += 1
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
        for m in MCP_PAIR_RE.finditer(text):  # JSONC / trailing commas: still read "key": "value" pairs
            state.tick()
            key, value = m.group(1), _strip_scheme(m.group(2))
            if NAMED_KEY_RE.search(value) or any(True for _ in find_jwts(value)) or not is_generic_token(value):
                continue
            check = _mcp_check_for(key)
            if _cap(counter, check):
                state.add(check, sf.rel, line_of(text, m.start()), key)
        return
    stack = [("", data, 0)]
    nodes = 0
    while stack:
        key, node, depth = stack.pop()
        nodes += 1
        if nodes > MCP_MAX_NODES or depth > MCP_MAX_DEPTH:
            state.gaps["q1"] += 1
            state.partial = True
            state.stats["mcp_capped"] += 1
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
                state.gaps["q1"] += 1
                continue
            if NAMED_KEY_RE.search(value) or any(True for _ in find_jwts(value)):
                check = "mcp-token"
            elif is_generic_token(_strip_scheme(value)):
                check = _mcp_check_for(key)
            else:
                continue
            if _cap(counter, check):
                state.add(check, sf.rel, 0, key)


def _finditer_lines(regex, text, sf, state, check, counter, snippet_fn=None):
    for m in regex.finditer(text):
        state.tick()
        if not _cap(counter, check):
            break
        snippet = snippet_fn(m) if snippet_fn else make_snippet(text, m.start(), m.end())
        state.add(check, sf.rel, line_of(text, m.start()), snippet)


def _clause(m):
    return m.group(0)[:MAX_SNIPPET]


def detect_sql(sf, state, opts):
    counter = {}
    text = _strip_sql_comments(sf.text)
    _finditer_lines(RLS_DISABLED_RE, text, sf, state, "rls-disabled", counter, _clause)
    for m in USING_TRUE_RE.finditer(text):
        state.tick()
        # a public-read policy (`for select using (true)`) is a design choice the by-hand test decides;
        # `for all`, insert/update/delete, or no FOR clause opens writes and is a no
        window = QUOTED_SQL_RE.sub(lambda q: " " * len(q.group(0)), text[max(0, m.start() - 2000):m.start()]).lower()
        cp = window.rfind("create policy")
        ap = window.rfind("alter policy")
        if ap > cp:
            check = "policy-altered-true"  # the statement being altered may well be read-only; the by-hand test decides
        elif cp >= 0 and POLICY_SELECT_RE.search(window[cp:]):
            check = "policy-select-true"
        else:
            check = "policy-using-true"
        if _cap(counter, check):
            state.add(check, sf.rel, line_of(text, m.start()), _clause(m))
    _finditer_lines(WITH_CHECK_TRUE_RE, text, sf, state, "policy-with-check-true", counter, _clause)
    _finditer_lines(POLICY_TO_ANON_RE, text, sf, state, "policy-to-anon", counter, _clause)
    _finditer_lines(STORAGE_BUCKET_TRUE_RE, text, sf, state, "storage-bucket-public-sql", counter, _clause)
    _finditer_lines(CRON_SQL_RE, text, sf, state, "cron-schedule", counter, _clause)
    for n, m in enumerate(CREATE_TABLE_RE.finditer(text)):
        if n >= MAX_ENV_NAME_MATCHES:
            break
        state.tick()
        name = _public_table(m.group(1))
        if name and name not in state.tables and len(state.tables) < MAX_SEEN:
            state.tables[name] = (sf.rel, line_of(text, m.start()))
    for n, m in enumerate(ENABLE_RLS_RE.finditer(text)):
        if n >= MAX_ENV_NAME_MATCHES:
            break
        state.tick()
        name = _public_table(m.group(1))
        if name and len(state.rls_enabled) < MAX_SEEN:
            state.rls_enabled.add(name)


def _public_table(raw):
    """`public.profiles`, `"Notes"`, `profiles` -> the name Postgres stores; tables in other schemas -> None.

    Each part folds on its own: unquoted to lower case, quoted kept exactly (`"public".Profiles` is `profiles`)."""
    parts = []
    for p in raw.split("."):
        p = p.strip()
        parts.append(p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p.lower())
    if len(parts) == 2:
        if parts[0] != "public":
            return None
        parts = parts[1:]
    return parts[0] or None


SQL_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
QUOTED_SQL_RE = re.compile(r"\"[^\"\n]*\"|'[^'\n]*'")  # identifiers and strings never name a FOR clause
MCP_PAIR_RE = re.compile(r'"([^"\n]{1,80})"[ \t]*:[ \t]*"([^"\n]{32,8192})"')


def _blank_block_comments(text):
    """Blank /* ... */ comments with a linear find loop (a lazy regex is quadratic on unclosed openers).

    Newlines are kept so line numbers hold; an unclosed opener leaves the rest visible, so a decisive
    line can never be hidden behind a comment that never ends.
    """
    out = []
    i = 0
    while True:
        j = text.find("/*", i)
        if j < 0:
            out.append(text[i:])
            break
        k = text.find("*/", j + 2)
        if k < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        out.append(re.sub(r"[^\n]", " ", text[j:k + 2]))
        i = k + 2
    return "".join(out)


def _strip_sql_comments(text):
    """Blank out comments (keeping newlines so line numbers hold) before the decisive Q3 checks."""
    text = _blank_block_comments(text)
    return SQL_LINE_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), text)


def _strip_slash_comments(text):
    text = _blank_block_comments(text)
    return SLASH_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), text)


def detect_rules(sf, state, opts):
    counter = {}
    # JSON rules files have no // comments, and a URL inside a string would eat the rest of the line
    text = _blank_block_comments(sf.text) if sf.base.lower().endswith(".json") else _strip_slash_comments(sf.text)
    for regex in (FIREBASE_ALLOW_TRUE_RE, FIREBASE_ALLOW_ALL_RE):
        for m in regex.finditer(text):
            state.tick()
            check = "firebase-rules-open" if FIREBASE_WRITE_RE.search(m.group(1)) else "firebase-rules-public-read"
            if _cap(counter, check):
                state.add(check, sf.rel, line_of(text, m.start()), _clause(m))
    _finditer_lines(RTDB_WRITE_OPEN_RE, text, sf, state, "firebase-rules-open", counter, _clause)
    _finditer_lines(RTDB_READ_OPEN_RE, text, sf, state, "firebase-rules-public-read", counter, _clause)


def detect_supabase_config(sf, state, opts):
    _finditer_lines(TOML_PUBLIC_TRUE_RE, sf.text, sf, state, "storage-bucket-public", {})


def _env_name(state, rel, name, line):
    name = name.strip().lower()
    if not ENV_NAME_RE.match(name) or name in IGNORED_ENV_NAMES:
        return
    state.env_names.add(name)
    state.add("env-name", rel, line, name)


def _env_matches(state, sf, regex, text):
    """Bounded pass over environment-name matches: capped, deadline-ticked, line numbers counted incrementally."""
    pos = 0
    line = 1
    for n, m in enumerate(regex.finditer(text)):
        if n >= MAX_ENV_NAME_MATCHES:
            break
        state.tick()
        line += text.count("\n", pos, m.start())
        pos = m.start()
        _env_name(state, sf.rel, m.group(1), line)


def detect_env_names(sf, state, opts):
    text = sf.text
    b = sf.base.lower()
    if b == "netlify.toml":
        _env_matches(state, sf, NETLIFY_CONTEXT_RE, text)
    elif b == "wrangler.toml":
        _env_matches(state, sf, WRANGLER_ENV_RE, text)
        m = CRON_WRANGLER_RE.search(text)
        if m:
            state.add("cron-schedule", sf.rel, line_of(text, m.start()), _clause(m))
    elif b == "vercel.json":
        _env_matches(state, sf, VERCEL_ENV_RE, text)
        m = CRON_VERCEL_RE.search(text)
        if m:
            state.add("cron-schedule", sf.rel, line_of(text, m.start()), _clause(m))


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
    state.manifests += 1
    state.dependencies += len(names)
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
    if "env" in sf.kinds or "env-template" in sf.kinds:
        return  # env lines are never echoed; the variable name above is all the hint needed
    _finditer_lines(MODEL_LITERAL_RE, text, sf, state, "model-literal", counter, _clause)
    _finditer_lines(SPEND_CAP_RE, text, sf, state, "spend-cap-word", counter, lambda m: m.group(0))
    _finditer_lines(HEALTH_ROUTE_RE, text, sf, state, "health-route", counter, _clause)


def detect_workflow(sf, state, opts):
    _finditer_lines(CRON_WORKFLOW_RE, sf.text, sf, state, "cron-schedule", {}, lambda m: "cron")
    if not REVIEW_NAME_RE.search(sf.base.lower()):  # a file already named for review has its row from the layout pass
        _finditer_lines(REVIEW_ACTION_RE, sf.text, sf, state, "review-workflow", {}, lambda m: m.group(1))


def detect_pii_schema(sf, state, opts):
    seen = set()
    ordinary = 0
    stopline = 0
    text = _strip_sql_comments(sf.text) if "sql" in sf.kinds else _strip_slash_comments(sf.text)
    text = CAMEL_SPLIT_RE.sub("_", text)  # dateOfBirth -> date_Of_Birth so the stop-line vocabulary matches camelCase too
    for m in PII_FIELD_RE.finditer(text):
        state.tick()
        field = m.group(1).lower()
        if field in seen:
            continue
        seen.add(field)
        if field in STOPLINE_FIELDS:
            # stop-line vocabulary is never crowded out by ordinary fields
            stopline += 1
            if stopline > MAX_HITS_PER_FILE_PER_CHECK:
                continue
        else:
            ordinary += 1
            if ordinary > 3:
                continue
        state.add("pii-field", sf.rel, line_of(text, m.start()), field)


def _pii_input_token(m):
    """Map HTML autocomplete-style names onto the stop-line vocabulary the skill knows."""
    name = m.group(1).lower()
    if name.startswith("cc-"):
        return "card_number" if "number" in name else "credit_card"
    return {"bday": "dob", "tel": "phone"}.get(name, name)


def detect_pii_inputs(sf, state, opts):
    _finditer_lines(PII_INPUT_RE, sf.text, sf, state, "pii-form-input", {}, _pii_input_token)


def detect_readme(sf, state, opts):
    _finditer_lines(BUILDER_URL_RE, sf.text, sf, state, "builder-readme", {}, lambda m: m.group(0).lower())


def _pred_code_or_env(sf):
    return "code" in sf.kinds or "env" in sf.kinds or "env-template" in sf.kinds or "html" in sf.kinds or "toml" in sf.kinds or "yaml" in sf.kinds or ("json" in sf.kinds and "mcp" not in sf.kinds and sf.base.lower() != "package.json")


def _q1_gate(sf, opts):
    return _pred_code_or_env(sf) and bool(opts.prefilter_re.search(sf.text))


DETECTORS = [
    (lambda sf: "mcp" in sf.kinds, detect_mcp),
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
    app_rel = lower[4:] if lower.startswith("src/") else lower
    if any(app_rel.startswith(p) for p in API_ROUTE_PREFIXES):
        state.add("api-route-dir", rel, 0, "")
    if FRAMEWORK_CONFIG_RE.match(b):
        state.add("framework-config", rel, 0, "")
    if any(d in AUTH_SEGMENTS for d in dirs) or stem in AUTH_SEGMENTS or "[...nextauth]" in lower:
        state.add("auth-path", rel, 0, "")
    fly = FLY_ENV_TOML_RE.match(b)
    is_deploy = b in DEPLOY_CONFIG_BASENAMES or (len(dirs) >= 2 and dirs[0] == ".github" and dirs[1] == "workflows" and (b.endswith(".yml") or b.endswith(".yaml"))) or bool(fly)
    if is_deploy:
        state.deploy_configs.append(rel)
        state.add("deploy-config", rel, 0, "")
    if b in PREVIEW_DEFAULTS and not dirs:
        state.add("preview-deploys-default", rel, 0, PREVIEW_DEFAULTS[b])
    if (len(dirs) >= 2 and dirs[0] == ".github" and dirs[1] == "workflows" and REVIEW_NAME_RE.search(b) and (b.endswith(".yml") or b.endswith(".yaml"))) \
            or b in (".coderabbit.yaml", ".coderabbit.yml"):
        state.add("review-workflow", rel, 0, "")
    if fly:
        _env_name(state, rel, fly.group(1), 0)
    m = re.match(r"^\.env\.([a-z0-9_-]+)$", b)
    in_examples = bool(TEST_PATH_RE.search(rel)) or any(d.lower() in ("docs", "doc", "examples", "example", "samples", "sample") for d in dirs)
    if m and not is_env_template(b) and not in_examples:
        _env_name(state, rel, m.group(1), 0)
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
        r = subprocess.run(["/usr/bin/xcode-select", "-p"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return True


def _git_dir(toplevel):
    dot = os.path.join(toplevel, ".git")
    if os.path.islink(dot):
        return dot
    if os.path.isdir(dot):
        return dot
    try:
        if os.path.getsize(dot) > 4096:
            return dot  # git itself rejects gitfiles this large; never read one into memory
        with open(dot, "r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline(4096).strip()
        if first.startswith("gitdir:"):
            target = first[len("gitdir:"):].strip()
            return target if os.path.isabs(target) else os.path.join(toplevel, target)
    except OSError:
        pass
    return dot


# A repository's own config is attacker-controlled, so it is parsed strictly (a stray carriage return,
# a continuation line, or a key sharing its section header's line means "cannot be read safely") and then
# judged against the directives that let git read, write or run something outside the scanned tree.
# Everything else is ordinary repository furniture: submodules, LFS, GUI settings and the like all pass.
GIT_DENY_SECTIONS = {"include", "includeif", "alias", "uploadpack", "receive", "protocol", "url", "safe", "advice"}
GIT_DENY_KEYS = {
    # Only what a `-c` override on the command line cannot already neutralise, and only what could make
    # one of our four read-only commands touch something outside the folder. core.hooksPath, fsmonitor,
    # pager, sshCommand and credential.helper are blanked on every call, so a repo setting them (husky
    # does) is ordinary furniture and must not cost the founder their git facts.
    "core": {"worktree", "alternaterefscommand", "gitproxy", "askpass"},
    "extensions": {"worktreeconfig", "partialclone", "objectformat", "refstorage", "compatobjectformat"},
    "remote": {"promisor", "partialclonefilter", "uploadpack", "receivepack", "proxy", "vcs", "gitproxy"},
}
GIT_TREE_MAX_ENTRIES = 100000


def _git_config_safe(text):
    """True when the config parses cleanly and names no directive that could send git outside the tree."""
    text = text.replace("\r\n", "\n")
    if "\r" in text:
        return False  # git treats a lone CR as whitespace; a line-based check cannot
    section = None
    for raw in text.split("\n"):
        line = raw.strip(" \t")
        if not line or line[0] in "#;":
            continue
        if line.endswith("\\"):
            return False  # a continuation hides the next physical line from this parser
        if line.startswith("["):
            close = line.find("]")
            if close < 0:
                return False
            rest = line[close + 1:].strip(" \t")
            if rest and rest[0] not in "#;":
                return False  # `[core]worktree=/x` on one line
            header = line[1:close].strip()
            name = header.split(None, 1)[0].split(".", 1)[0].lower() if header else ""
            if not name or name in GIT_DENY_SECTIONS:
                return False
            section = name
            continue
        if section is None:
            return False
        key = re.split(r"[ \t=]", line, 1)[0].lower()
        if key in GIT_DENY_KEYS.get(section, ()):
            return False
    return True


def _git_tree_plain(gitdir, state=None):
    """Everything git will open under refs/, logs/ and objects/ is a plain file or directory (no fifo, no link)."""
    seen = 0
    for sub in ("refs", "logs", "objects"):
        top = os.path.join(gitdir, sub)
        if not os.path.isdir(top):
            continue
        for root, dirs, files in os.walk(top, followlinks=False, onerror=lambda e: None):
            if state is not None and state.deadline is not None and time.monotonic() > state.deadline:
                return False
            for name in dirs + files:
                seen += 1
                if seen > GIT_TREE_MAX_ENTRIES:
                    return False
                try:
                    st = os.lstat(os.path.join(root, name))
                except OSError:
                    return False
                if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode)):
                    return False
    return True


def _enclosing_git_root(real_repo):
    """The nearest folder at or above the app that holds a .git entry, found without running git."""
    home = os.path.realpath(os.path.expanduser("~"))
    d = real_repo
    while True:
        if os.path.lexists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        # never climb past the home directory: a dotfiles repo at ~ is not this app's history
        if parent == d or d == home or parent == home:
            return None
        d = parent


GIT_DIR_ENTRIES = ("HEAD", "config", "shallow", "packed-refs", "index", "objects", "refs", "hooks", "info", "logs")
GIT_CONFIG_MAX_BYTES = 65536


def _read_small_regular(path, limit):
    """Read a plain regular file of at most `limit` bytes without following symlinks or blocking on a fifo; None otherwise."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError:
        return None
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > limit:
            return None
        return read_bytes(fd, st.st_size)
    except OSError:
        return None
    finally:
        os.close(fd)


def _git_pointer_ok(real_repo, state=None):
    """Refuse any .git that could make git read, write, or run something outside the scanned tree.

    A symlinked .git, a gitfile pointing outside the tree (worktrees included) or larger than git itself
    accepts, a git directory carrying commondir / gitdir / alternates pointers, any symlink or special file
    among the entries git touches, and a config that is unreadable, oversized, or carries worktree /
    include / promisor / hook / helper directives all mean "not a repository we will ask git about".
    The gitfile's target is checked the same way, so one level of indirection buys nothing.
    """
    dot = os.path.join(real_repo, ".git")
    try:
        st = os.lstat(dot)
    except OSError:
        return True  # no .git here at all; git may still find an enclosing repository (subdir mode)
    if stat.S_ISLNK(st.st_mode):
        return False
    if stat.S_ISREG(st.st_mode):
        if st.st_size > 4096:
            return False
        target = os.path.realpath(_git_dir(real_repo))
        if not (target == real_repo or target.startswith(real_repo + os.sep)):
            return False
        gitdir = target
    elif stat.S_ISDIR(st.st_mode):
        gitdir = dot
    else:
        return False
    if os.path.islink(gitdir) or not os.path.isdir(gitdir):
        return False
    for pointer in ("commondir", "gitdir", "config.worktree", os.path.join("objects", "info", "alternates")):
        if os.path.lexists(os.path.join(gitdir, pointer)):
            return False
    for entry in GIT_DIR_ENTRIES:
        try:
            est = os.lstat(os.path.join(gitdir, entry))
        except OSError:
            continue
        if not (stat.S_ISREG(est.st_mode) or stat.S_ISDIR(est.st_mode)):
            return False
    cfg = os.path.join(gitdir, "config")
    if os.path.lexists(cfg):
        data = _read_small_regular(cfg, GIT_CONFIG_MAX_BYTES)
        if data is None:
            return False  # unreadable, symlinked, special, or oversized: never fail open
        if not _git_config_safe(data.decode("utf-8", errors="replace")):
            return False
    return _git_tree_plain(gitdir, state)


def _trusted_git(real_repo):
    """The first git on PATH that does not live inside the scanned tree or the current directory."""
    try:
        cwd = os.path.realpath(os.getcwd())
    except OSError:
        cwd = ""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        # relative PATH entries ("." included) resolve against the launch folder, which sits next to the untrusted app
        if not entry or not os.path.isabs(entry):
            continue
        for name in ("git", "git.exe"):
            candidate = os.path.join(entry, name)
            if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
                continue
            real = os.path.realpath(candidate)
            if real.startswith(real_repo + os.sep):
                continue
            if cwd and os.path.dirname(real) == cwd:
                continue  # a git sitting in the launch folder itself is not a system git
            return real
    return None


def _git_unread(state, check, text):
    """Git was not consulted: say why, mark the scan partial, and make sure Q1 cannot look clean."""
    state.add(check, "", 0, text)
    state.add("git-index-unread", "", 0, "git's file index was not read, so committed secrets could not be checked")
    state.partial = True
    state.stats["git_index_partial"] += 1


def git_facts(repo, state):
    real_repo = os.path.realpath(repo)
    root = _enclosing_git_root(real_repo)
    if root is None:
        state.add("git-not-a-repo", "", 0, "not a git repository")
        return
    if not _git_pointer_ok(root, state):
        _git_unread(state, "git-config-not-vouched", "this repository's git settings could not be vouched for, so git was not run")
        return
    git_bin = _trusted_git(real_repo)
    if git_bin is None:
        _git_unread(state, "git-unavailable", "git is not installed")
        return
    if sys.platform == "darwin" and git_bin == "/usr/bin/git" and not _darwin_git_ready():
        _git_unread(state, "git-unavailable", "git needs the Xcode Command Line Tools")
        return
    base = [git_bin, "-c", "core.fsmonitor=", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat", "-c", "core.sshCommand=", "-c", "credential.helper=", "-C", real_repo]
    env = dict((k, v) for k, v in os.environ.items() if not k.startswith("GIT_"))
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_CONFIG_NOSYSTEM="1",
               GIT_CEILING_DIRECTORIES=os.path.dirname(root))  # discovery can never pass the folder guarded above
    started = time.monotonic()

    class _Result(object):
        def __init__(self, returncode, stdout, truncated):
            self.returncode = returncode
            self.stdout = stdout
            self.truncated = truncated

    def run(args):
        """Run git with a shared time budget and a hard cap on captured output."""
        remaining = GIT_BUDGET_S - (time.monotonic() - started)
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, GIT_BUDGET_S)
        proc = subprocess.Popen(base + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, env=env,
                                start_new_session=_HAS_NONBLOCK)

        def kill_tree():
            if _HAS_NONBLOCK:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)  # grandchildren (a fetch git spawned) die with it
                except Exception:
                    pass
            try:
                proc.kill()
            except Exception:
                pass

        try:
            chunks = []
            got = 0
            truncated = False
            end_at = time.monotonic() + max(1.0, remaining)
            if not _HAS_NONBLOCK:  # Windows before 3.12: no non-blocking pipes, so read on a thread under the same caps
                box = {"got": 0, "truncated": False}

                def reader():
                    try:
                        while True:
                            chunk = proc.stdout.read1(65536)
                            if not chunk:
                                return
                            chunks.append(chunk)
                            box["got"] += len(chunk)
                            if box["got"] >= GIT_OUTPUT_LIMIT:
                                box["truncated"] = True
                                kill_tree()
                                return
                    except Exception:
                        return  # a closed pipe is the caller giving up, never a traceback on stderr

                worker = threading.Thread(target=reader, daemon=True)
                worker.start()
                worker.join(max(1.0, remaining))
                if worker.is_alive():
                    kill_tree()
                    worker.join(2)  # let the reader leave the pipe before the caller closes it
                    raise subprocess.TimeoutExpired(args, GIT_BUDGET_S)
                proc.wait(timeout=2)
                return _Result(proc.returncode, b"".join(chunks)[:GIT_OUTPUT_LIMIT].decode("utf-8", errors="replace"), box["truncated"])
            fd = proc.stdout.fileno()
            os.set_blocking(fd, False)
            while True:
                wait = end_at - time.monotonic()
                if wait <= 0:
                    kill_tree()
                    raise subprocess.TimeoutExpired(args, GIT_BUDGET_S)
                ready, _, _ = select.select([fd], [], [], min(wait, 0.5))
                if not ready:
                    continue
                try:
                    chunk = os.read(fd, min(65536, GIT_OUTPUT_LIMIT))
                except BlockingIOError:
                    continue
                if not chunk:
                    break
                chunks.append(chunk)
                got += len(chunk)
                if got >= GIT_OUTPUT_LIMIT:
                    truncated = True
                    kill_tree()
                    break
            proc.wait(timeout=max(1.0, end_at - time.monotonic()))
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            if proc.poll() is None:
                kill_tree()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
        return _Result(proc.returncode, b"".join(chunks)[:GIT_OUTPUT_LIMIT].decode("utf-8", errors="replace"), truncated)

    try:
        top = run(["rev-parse", "--show-toplevel"])
        if top.returncode != 0:
            state.add("git-not-a-repo", "", 0, "not a git repository")
            return
        toplevel = os.path.realpath(top.stdout.strip())
        if not _git_pointer_ok(toplevel, state):
            _git_unread(state, "git-config-not-vouched", "this repository's git settings could not be vouched for, so git was not run")
            return
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
        tracked = run(["ls-files", "-z", "--", ":(icase).env*", ":(icase)*/.env*", ":(icase)*.env", ":(icase)*/*.env"])  # index-only and decisive: first inside the budget
        names = []
        if tracked.truncated:
            state.partial = True
            state.stats["git_index_partial"] += 1
        if tracked.returncode == 0 or tracked.truncated:
            for p in tracked.stdout.split("\0"):
                if not p:
                    continue
                b = p.rsplit("/", 1)[-1]
                if is_env_file(b) and b.lower() != ".envrc":  # .envrc (direnv) is committed on purpose
                    names.append(p)
        names = sorted(names)
        if tracked.returncode != 0 and not tracked.truncated:
            state.git["tracked_env_files"] = None  # the index could not be read: fall back to the on-disk check
            state.partial = True
            state.stats["git_index_partial"] += 1
        else:
            state.git["tracked_env_files"] = [sanitize_path(p) for p in names[:MAX_TRACKED_ENV_FILES]]
        for p in names:
            b = p.rsplit("/", 1)[-1].lower()
            stem = (b[:-len(".env")] if b.endswith(".env") and not b.startswith(".env") else b[len(".env"):]).strip("._-")
            check = "tracked-env-file-nonprod" if stem in NONPROD_ENV_STEMS else "tracked-env-file"
            state.add(check, p, 0, "")
        tags = run(["for-each-ref", "--count=1000", "--format=%(refname)", "refs/tags"])
        state.git["tags"] = len([t for t in tags.stdout.splitlines() if t.strip()]) if tags.returncode == 0 else 0
        shallow = run(["rev-parse", "--is-shallow-repository"])
        state.git["shallow"] = shallow.stdout.strip() == "true" or _read_small_regular(os.path.join(_git_dir(toplevel), "shallow"), 4096) is not None
        commits = run(["rev-list", "--count", "--exclude-promisor-objects", "HEAD"])  # the only object walk: last, never lazy-fetching
        state.git["commits"] = int(commits.stdout.strip()) if commits.returncode == 0 and commits.stdout.strip().isdigit() else 0
        if subdir:
            state.add("git-subdir", "", 0, "the app folder is inside a larger repository")
        if state.git["shallow"]:
            state.add("git-shallow", "", 0, "shallow clone")
        state.add("git-history", "", 0, "%d commits, %d tags" % (state.git["commits"], state.git["tags"]))
    except subprocess.TimeoutExpired:
        state.git["commits"] = None  # keep the index facts already gathered; history stays unknown
        state.git["tags"] = None
        state.git["shallow"] = None
        if state.git["tracked_env_files"] is None:
            _git_unread(state, "git-timeout", "git did not answer in time")
        else:
            state.add("git-timeout", "", 0, "git did not answer in time")
    except Exception:
        state.git = _empty_git()
        _git_unread(state, "git-unavailable", "git could not be run")


# --------------------------------------------------------------------- walk

def _walk_key(name):
    """Known source roots are walked first so a file cap never runs out on assets before src/ is read."""
    return (0 if name.lower() in SOURCE_ROOTS else 1, name)


def run_scan(repo, state, opts):
    state.stats["config"] = {"exclude_dirs_added": list(opts.exclude_dirs_added), "browser_prefixes_added": list(opts.browser_prefixes_added)}
    real_repo = os.path.realpath(repo)
    deadline = time.monotonic() + opts.deadline_s
    state.deadline = deadline
    total_bytes = 0
    candidates = 0
    stop = False
    git_facts(repo, state)
    git_present = state.git["tracked_env_files"] is not None

    def unreadable(err):
        state.stats["dirs_unreadable"] += 1
        state.partial = True

    for dirpath, dirnames, filenames in os.walk(real_repo, topdown=True, followlinks=False, onerror=unreadable):
        if stop:
            break
        if time.monotonic() > deadline:
            state.stats["deadline_hit"] = True
            state.partial = True
            break
        rel_dir = os.path.relpath(dirpath, real_repo).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        parent_name = os.path.basename(dirpath)
        real_dir = os.path.realpath(dirpath)
        if real_dir != real_repo and not real_dir.startswith(real_repo + os.sep):
            dirnames[:] = []
            continue
        if len(dirnames) + len(filenames) > MAX_DIR_ENTRIES:
            # subdirectories keep priority (an api/ folder matters more than the 50,001st file)
            state.partial = True
            state.stats["dirs_truncated"] += 1
            dirnames[:] = sorted(dirnames, key=_walk_key)[:MAX_DIR_ENTRIES]
            filenames = sorted(filenames)[:max(0, MAX_DIR_ENTRIES - len(dirnames))]
        keep = []
        for d in sorted(dirnames, key=_walk_key):
            full = os.path.join(dirpath, d)
            if d.lower() in EXCLUDED_DIRS:
                if d.lower() in BUILD_OUTPUT_DIRS:
                    state.add("build-output-unread", (rel_dir + "/" + d) if rel_dir else d, 0, "")  # evidence, so Q1 stays Don't know
                continue
            try:
                if os.path.islink(full):
                    state.stats["files_skipped_special"] += 1
                    note_unread_dir(state)  # a linked folder is not read, so nothing in it was looked at
                    continue
            except OSError:
                note_unread_dir(state)
                continue
            if is_never_open_dir(d, parent_name):
                state.stats["files_never_open"] += count_files(full, deadline)
                continue
            if d.lower() in opts.excluded:
                note_unread_dir(state)  # the founder asked for this folder to be skipped
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
                state.stats["files_errored"] += 1
                note_unread(state, name, os.path.splitext(name)[1].lower())
                state.partial = True
                continue
            if stat.S_ISREG(st.st_mode) and st.st_nlink > 1:
                state.stats["files_skipped_hardlink"] += 1
                note_unread(state, name, os.path.splitext(name)[1].lower())
                state.partial = True
                continue
            if not stat.S_ISREG(st.st_mode):
                state.stats["files_skipped_special"] += 1
                note_unread(state, name, os.path.splitext(name)[1].lower())
                continue
            if candidates >= opts.max_files:
                state.stats["max_files_hit"] = True
                state.partial = True
                stop = True
                break
            base = name
            ext = os.path.splitext(name)[1].lower()
            layout_checks(rel, base, state)
            if not git_present and is_env_file(name) and name.lower() != ".envrc":
                state.add("env-file-on-disk", rel, 0, "")
            if is_generated(name):
                state.stats["files_skipped_generated"] += 1
                if name.lower().endswith(GENERATED_CODE_SUFFIXES):
                    state.gaps["q1"] += 1  # a public bundle is exactly what the browser downloads
                continue
            if st.st_size > opts.max_file_bytes:
                skip_oversize(state, base, ext)
                continue
            opened = open_regular(full)
            if opened is None:
                state.stats["files_skipped_special"] += 1
                note_unread(state, base, ext)
                continue
            fd, size = opened
            try:
                if size > opts.max_file_bytes:
                    skip_oversize(state, base, ext)
                    continue
                if total_bytes + size > opts.max_total_bytes:
                    state.stats["max_total_bytes_hit"] = True
                    state.partial = True
                    stop = True
                    break
                data = read_bytes(fd, size)
            finally:
                os.close(fd)
            if len(data) < size:  # the file shrank or was swapped after fstat: never treat a short read as the whole file
                state.stats["files_errored"] += 1
                state.partial = True
                continue
            total_bytes += len(data)
            candidates += 1
            text = decode_text(data)
            if text is None:
                state.stats["files_skipped_binary"] += 1
                note_unread(state, base, ext)
                if could_hold_q1_q3(base, ext):
                    state.partial = True  # a source, config, rules or env file that looks binary is itself worth a look
                continue
            try:
                cls, kinds = classify(rel, base, ext, text)
                sf = ScanFile(rel, base, ext, cls, kinds, text)
                if "code" in kinds or "html" in kinds:
                    state.cls_counts[cls] += 1
                if _pred_code_or_env(sf) or "mcp" in kinds:
                    state.q1_files += 1
                if kinds & {"sql", "rules"}:
                    state.rule_files += 1
                if _q1_gate(sf, opts):
                    claimed = []
                    detect_browser_prefix(sf, state, opts, claimed)
                    detect_key_literals(sf, state, opts, claimed)
                for predicate, detector in DETECTORS:
                    if predicate(sf):
                        detector(sf, state, opts)
                state.files_scanned += 1
            except Deadline:
                state.stats["deadline_hit"] = True
                state.partial = True
                stop = True
                break
            except Exception:
                state.stats["files_errored"] += 1
                state.partial = True
    return state


# ----------------------------------------------------------------- resolver

def _q(answer, confidence, evidence):
    return {"answer": answer, "confidence": confidence, "evidence": list(evidence)}


def _n(count, noun, plural=None):
    return "%d %s" % (count, noun if count == 1 else (plural or noun + "s"))


def _row(check, snippet):
    """A row the resolver writes about the scan itself: no path, no line, never app text."""
    return {"path": "", "line": 0, "snippet": sanitize(snippet), "check": check}


def resolve(state):
    """`nothing-found` means the scanner read the files that could answer and every check came back empty.
    It is only ever claimed on a complete scan, never on a question the walk had nothing to read for, and
    it is never a `no`: a founder told "nothing found" still has the by-hand test to run."""
    ev = state.evidence
    ef = state.effects
    out = {}
    complete = not state.partial  # a folder the founder excluded is a gap on every question (note_unread_dir)
    for name in sorted(set(state.tables) - state.rls_enabled)[:MAX_HITS_PER_FILE_PER_CHECK]:
        path, line = state.tables[name]
        state.add("table-without-rls", path, line, name)  # a table no migration turns row level security on for

    def summary(key, tail=""):
        if not ev[key]:
            return [_row("scan-summary", "%d files scanned, 0 hits%s" % (state.files_scanned, tail))]
        return ev[key]

    if "no" in ef["q1"]:
        out["q1"] = _q("no", "high", ev["q1"])
    elif complete and not ev["q1"] and state.q1_files and not state.gaps["q1"]:
        env = "no tracked env file" if state.git["tracked_env_files"] is not None else "no env file"
        agents = "; %s not opened" % _n(state.stats["files_never_open"], "agent file") if state.stats["files_never_open"] else ""
        out["q1"] = _q("nothing-found", "med", [_row("nothing-found-keys", "%s read: no key in client code, no MCP token, %s%s" % (_n(state.q1_files, "file"), env, agents))])
    else:
        out["q1"] = _q("dont-know", "med", summary("q1"))
    if "no" in ef["q3"]:
        out["q3"] = _q("no", "high", ev["q3"])
    elif complete and not ev["q3"] and state.rule_files and not state.gaps["q3"]:
        out["q3"] = _q("nothing-found", "med", [_row("nothing-found-rules", "%s read: no RLS disabled, no using (true), no open Firebase rule" % _n(state.rule_files, "rule file"))])
    else:
        out["q3"] = _q("dont-know", "med", summary("q3", "" if state.rule_files else "; no SQL or security-rules file among them"))
    q2 = list(ev["q2"])
    code_files = sum(state.cls_counts.values())
    if code_files:
        c = state.cls_counts
        q2.insert(0, _row("client-server-split", "%d code files: %d as browser code, %d as server code, %d unclear" % (code_files, c["client"], c["server"], c["other"])))
    out["q2"] = _q("dont-know", "med" if ev["q2"] else "low", q2[:MAX_EVIDENCE])  # the split alone is not a hint
    out["q8"] = _q("dont-know", "med" if ev["q8"] else "low", ev["q8"])
    if complete and not ev["q9"] and state.dependencies and not state.gaps["q9"]:
        out["q9"] = _q("nothing-found", "med", [_row("nothing-found-monitoring", "%s read: no error tracking, no Sentry config, no health route, no cron" % _n(state.dependencies, "dependency", "dependencies"))])
    else:
        out["q9"] = _q("dont-know", "med" if ev["q9"] else "low", ev["q9"])
    for key in ("q4", "q7", "q10"):
        out[key] = _q("dont-know", "low", ev[key])
    q11 = list(ev["q11"])
    if state.git["commits"]:
        q11.insert(0, _row("code-history-local", "the code is on this machine with %d commits; the data export is yours to check" % state.git["commits"]))
    out["q11"] = _q("dont-know", "low", q11[:MAX_EVIDENCE])
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
        hinted = [e for e in ev["q6"] if e["check"] != "preview-deploys-default"]
        out["q6"] = _q("dont-know", "med" if hinted else "low", ev["q6"])
    ordered = {}
    for i in range(1, 12):
        ordered["q%d" % i] = out["q%d" % i]
    return ordered


def scan(repo, **kwargs):
    opts = Options(**kwargs)
    state = ScanState()
    run_scan(repo, state, opts)
    return build_result(state, repo)


def _fit_output(result):
    """Keep the JSON under the acceptance cap: drop evidence-only rows anywhere before any decisive `no` row anywhere."""
    dropped = 0
    while len(json.dumps(result, ensure_ascii=True, separators=(",", ":")).encode("utf-8")) > MAX_OUTPUT_BYTES:
        victim = None
        fallback = None
        for q in iter_questions(result):
            rows = q["evidence"]
            for i in range(len(rows) - 1, -1, -1):
                if CHECKS[rows[i]["check"]][1] != "no":
                    if victim is None or len(rows) > len(victim[0]):
                        victim = (rows, i)
                    break
            if rows and fallback is None:
                fallback = (rows, len(rows) - 1)
        target = victim or fallback
        if target is None:
            break
        del target[0][target[1]]
        dropped += 1
    if dropped:
        result["stats"]["output_trimmed"] = dropped
        result["partial"] = True
        for q in iter_questions(result):
            if q["answer"] == "nothing-found":  # never claimed on a partial result, however it became partial
                q["answer"] = "dont-know"
    return result


def build_result(state, repo):
    try:
        real_repo = os.path.realpath(repo)
        cwd = os.path.realpath(os.getcwd())
        if real_repo == cwd:
            state.warnings.append("repo-is-cwd")
        elif cwd.startswith(real_repo + os.sep):
            state.warnings.append("repo-contains-cwd")
    except OSError:
        pass
    return _fit_output({
        "ok": True,
        "partial": bool(state.partial),
        "version": __version__,
        "files_scanned": state.files_scanned,
        "stats": state.stats,
        "warnings": list(state.warnings),
        "git": state.git,
        "questions": resolve(state),
    })


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
    warnings.simplefilter("ignore")  # stderr carries exactly one summary line
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _Parser(prog="custody_scan.py", add_help=True, description="Read-only evidence gatherer for the eleven custody questions.")
    parser.add_argument("--repo", help="the app folder (run from the folder that contains it)")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument("--deadline-s", type=float, default=DEFAULT_DEADLINE_S)
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
        if args.max_files < 1 or args.max_file_bytes < 1 or args.max_total_bytes < 1 or not args.deadline_s > 0:
            sys.stderr.write("Limits must be positive: --max-files, --max-file-bytes, --max-total-bytes, --deadline-s\n")
            raise UsageError("non-positive limit")
        raw_repo = os.path.expanduser(args.repo.rstrip("/") or "/")
        if os.path.islink(raw_repo):
            emit(envelope("repo-is-symlink"), pretty)
            return 2 if exit_code else 0
        repo = os.path.realpath(raw_repo)
        if not os.path.exists(repo):
            emit(envelope("repo-not-found"), pretty)
            return 2 if exit_code else 0
        if not os.path.isdir(repo):
            emit(envelope("repo-not-a-directory"), pretty)
            return 2 if exit_code else 0
        if not os.access(repo, os.R_OK | os.X_OK):
            emit(envelope("repo-unreadable"), pretty)
            return 2 if exit_code else 0
        try:
            real_cwd = os.path.realpath(os.getcwd())
        except OSError:
            real_cwd = ""
        if real_cwd and real_cwd != repo and real_cwd.startswith(repo + os.sep):
            emit(envelope("repo-contains-cwd"), pretty)  # `..` from inside the app would walk everything above it
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
        try:
            emit(envelope("internal:" + type(exc).__name__), pretty)
        except Exception:
            pass
        return 2 if exit_code else 0


if __name__ == "__main__":
    sys.exit(main())
