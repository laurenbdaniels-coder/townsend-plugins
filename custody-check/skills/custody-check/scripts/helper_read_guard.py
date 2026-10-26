#!/usr/bin/env python3
"""PreToolUse guard on Read for custody-check's full-read helpers (S-068). Standard library only.

Claude Code runs this for every Read while the plugin is installed. It judges only Reads whose caller is the
plugin agent custody-check:full-read-helper; every other call gets no output and exit 0, so the founder's own
session and other agents are untouched. For a helper it denies a Read that:
  - is outside the working folder, or is not inside a folder under it (the app is <cwd>/<app>/...),
  - uses .., or resolves elsewhere through a link,
  - has no limit, or a limit over 400 lines,
  - names a file the check never opens (env, key, credential, instruction, lock and build files).
Input it cannot parse is denied (fail closed): Claude Code always sends JSON, so this never touches a normal call.
"""
import json
import os
import re
import sys

HELPER = "custody-check:full-read-helper"
MAX_LINES = 400

HERE = os.path.dirname(os.path.abspath(__file__))
_shared = {}
try:
    with open(os.path.join(HERE, "shared_rules.py"), encoding="utf-8") as fh:
        exec(compile(fh.read(), "shared_rules.py", "exec"), _shared)
except (OSError, SyntaxError):
    _shared = {}

NEVER_DIRS = set(_shared.get("NEVER_OPEN_DIRS", ())) | {".claude", ".codex", ".agents", ".cursor", ".windsurf", ".gemini",
                                                       "node_modules", "dist", "build", ".next", "out", "vendor", "coverage",
                                                       ".git", ".vercel", ".turbo"}
NEVER_DIR_PAIRS = set(_shared.get("NEVER_OPEN_DIR_PAIRS", ())) | {(".cursor", "rules"), (".github", "instructions"),
                                                                 (".github", "prompts"), (".github", "agents")}
NEVER_FILE_RE = _shared.get("NEVER_OPEN_FILE_RE") or re.compile(r"^(?:claude|agents?|gemini|conventions)\.md$|.*\.mdc$", re.I)
NEVER_FILES = set(_shared.get("NEVER_OPEN_FILES", ())) | {".cursorrules", ".windsurfrules"}

SECRET_FILE_RE = re.compile(
    r"^\.env(\..*)?$|.*\.env$|.*\.(pem|key|p12|pfx|p8|jks|keystore)$"
    r"|^serviceaccount.*\.json$|.*firebase-adminsdk.*\.json$|^credentials.*\.json$|^client_secret.*\.json$"
    r"|.*secret.*\.ya?ml$|^\.npmrc$|^\.pypirc$|^\.netrc$|^docker-compose.*\.ya?ml$|^id_(rsa|ed25519|ecdsa|dsa)$", re.I)
LOCK_RE = re.compile(r".*-lock\.(json|yaml)$|.*\.lock$|^npm-shrinkwrap\.json$", re.I)


def never_open(parts):
    """parts: a path inside the app, split on /. Returns why the check never opens it, or None.
    full_read_slices.py uses this too, so the slice plan and the guard share one list."""
    dirs, name = [p.lower() for p in parts[:-1]], parts[-1]
    for i, d in enumerate(dirs):
        if d in NEVER_DIRS or (i + 1 < len(dirs) and (d, dirs[i + 1]) in NEVER_DIR_PAIRS):
            return "a folder the check never opens"
    if name in NEVER_FILES or NEVER_FILE_RE.match(name) or SECRET_FILE_RE.match(name) or LOCK_RE.match(name):
        return "a file the check never opens"
    return None


def deny(reason):
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                        "permissionDecisionReason": "custody-check: " + reason}}))
    sys.exit(0)


def judge(payload):
    inp = payload.get("tool_input") or {}
    path = inp.get("file_path")
    cwd = payload.get("cwd") or os.getcwd()
    if not isinstance(path, str) or not path:
        deny("a helper Read needs a file path")
    limit = inp.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > MAX_LINES:
        deny("a helper Read needs a limit of at most %d lines" % MAX_LINES)
    raw = path.replace("\\", "/")
    if ".." in raw.split("/"):
        deny("a helper never uses ..")
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    root = os.path.realpath(cwd)
    real = os.path.realpath(full)
    try:
        rel = os.path.relpath(real, root)
    except ValueError:
        deny("outside the working folder")
    parts = rel.replace("\\", "/").split("/")
    if rel.startswith("..") or os.path.isabs(rel) or len(parts) < 2:
        deny("outside the app folder")
    why = never_open(parts[1:])
    if why:
        deny(why)


def main():
    data = sys.stdin.read()
    try:
        payload = json.loads(data)
    except ValueError:
        deny("could not read the hook input")
    if not isinstance(payload, dict):
        sys.exit(0)
    if payload.get("agent_type") != HELPER or payload.get("tool_name") != "Read":
        sys.exit(0)
    judge(payload)
    sys.exit(0)


if __name__ == "__main__":
    main()
