"""Tests for helper_read_guard.py: the PreToolUse Read guard for custody-check's full-read helpers (S-068)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "helper_read_guard.py")
HELPER = "custody-check:full-read-helper"


def run(payload, raw=None):
    data = raw if raw is not None else json.dumps(payload)
    p = subprocess.run([sys.executable, "-I", GUARD], input=data, capture_output=True, text=True, timeout=20)
    out = p.stdout.strip()
    decision = json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else None
    return p.returncode, decision


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.path.realpath(self.tmp.name)
        os.makedirs(os.path.join(self.cwd, "app", "src"))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, path, limit=200, agent=HELPER, tool="Read", **extra):
        inp = {"file_path": path}
        if limit is not None:
            inp["limit"] = limit
        inp.update(extra)
        payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": inp, "cwd": self.cwd}
        if agent is not None:
            payload["agent_type"] = agent
            payload["agent_id"] = "a1"
        return run(payload)

    def p(self, rel):
        return os.path.join(self.cwd, rel)

    # --- scope: only the helper is ever judged
    def test_main_session_never_judged(self):
        self.assertEqual(self.call(self.p("app/.env"), agent=None), (0, None))

    def test_other_agent_never_judged(self):
        self.assertEqual(self.call("/etc/passwd", agent="Explore"), (0, None))

    def test_other_tool_never_judged(self):
        self.assertEqual(self.call(self.p("app/.env"), tool="Grep"), (0, None))

    # --- allowed
    def test_plain_code_file_allowed(self):
        self.assertEqual(self.call(self.p("app/src/index.ts")), (0, None))

    def test_relative_path_inside_cwd_allowed(self):
        self.assertEqual(self.call("app/src/index.ts"), (0, None))

    def test_limit_400_allowed(self):
        self.assertEqual(self.call(self.p("app/src/a.ts"), limit=400), (0, None))

    # --- denied
    def test_outside_working_folder(self):
        self.assertEqual(self.call("/etc/passwd")[1], "deny")

    def test_cwd_itself_not_an_app_file(self):
        self.assertEqual(self.call(self.p("notes.txt"))[1], "deny")

    def test_dotdot(self):
        self.assertEqual(self.call(self.p("app/src/../../other/x.ts"))[1], "deny")

    def test_no_limit(self):
        self.assertEqual(self.call(self.p("app/src/a.ts"), limit=None)[1], "deny")

    def test_limit_over_400(self):
        self.assertEqual(self.call(self.p("app/src/a.ts"), limit=401)[1], "deny")

    def test_env_files(self):
        for name in (".env", ".env.local", ".env.production", ".env.example"):
            self.assertEqual(self.call(self.p("app/" + name))[1], "deny", name)

    def test_key_files(self):
        for name in ("server.pem", "id.key", "cert.p12", "AuthKey.p8"):
            self.assertEqual(self.call(self.p("app/" + name))[1], "deny", name)

    def test_credential_names(self):
        for name in ("serviceAccountKey.json", "my-firebase-adminsdk-x1.json", "credentials.json", "client_secret_123.json",
                     "secrets.yaml", "app-secret.yml", ".npmrc", ".pypirc", "docker-compose.yml", "docker-compose.prod.yaml"):
            self.assertEqual(self.call(self.p("app/config/" + name))[1], "deny", name)

    def test_instruction_files_and_folders(self):
        for rel in ("CLAUDE.md", "AGENTS.md", "docs/GEMINI.md", ".cursorrules", "x.mdc", ".claude/settings.json",
                    ".cursor/rules/a.md", ".github/instructions/a.md", ".github/prompts/p.md"):
            self.assertEqual(self.call(self.p("app/" + rel))[1], "deny", rel)

    def test_lockfiles_and_build_folders(self):
        for rel in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "node_modules/x/index.js",
                    "dist/a.js", ".next/server.js", "build/a.js", "vendor/a.php", "coverage/a.json"):
            self.assertEqual(self.call(self.p("app/" + rel))[1], "deny", rel)

    def test_symlink_out_of_folder(self):
        target = tempfile.mkdtemp()
        try:
            os.symlink(target, os.path.join(self.cwd, "app", "link"))
            self.assertEqual(self.call(self.p("app/link/secret.ts"))[1], "deny")
        finally:
            os.rmdir(target)

    # --- fail closed for the helper
    def test_bad_json_from_helper_context_denies(self):
        code, decision = run(None, raw="{not json")
        self.assertIn(code, (0, 2))
        self.assertEqual(code == 2 or decision == "deny", True)

    def test_missing_path_denies(self):
        payload = {"tool_name": "Read", "tool_input": {"limit": 10}, "cwd": self.cwd, "agent_type": HELPER}
        self.assertEqual(run(payload)[1], "deny")


class MissingSharedRulesTests(unittest.TestCase):
    """Without shared_rules.py next to it, the guard denies a helper Read and leaves every other call alone."""

    def setUp(self):
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        self.guard = os.path.join(self.tmp.name, "helper_read_guard.py")
        shutil.copy(GUARD, self.guard)
        os.makedirs(os.path.join(self.tmp.name, "app"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_copy(self, agent):
        payload = {"tool_name": "Read", "tool_input": {"file_path": os.path.join(self.tmp.name, "app", "a.ts"), "limit": 10},
                   "cwd": self.tmp.name}
        if agent:
            payload["agent_type"] = agent
        p = subprocess.run([sys.executable, "-I", self.guard], input=json.dumps(payload), capture_output=True, text=True)
        out = p.stdout.strip()
        return p.returncode, (json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else None)

    def test_helper_denied(self):
        self.assertEqual(self.run_copy(HELPER), (0, "deny"))

    def test_other_callers_untouched(self):
        self.assertEqual(self.run_copy(None), (0, None))


class HooksFileTests(unittest.TestCase):
    def test_hooks_json_points_at_guard(self):
        plugin = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
        with open(os.path.join(plugin, "hooks", "hooks.json")) as fh:
            cfg = json.load(fh)
        entries = cfg["hooks"]["PreToolUse"]
        self.assertTrue(any(e.get("matcher") == "Read" and any("helper_read_guard.py" in h["command"]
                                                                  for h in e["hooks"]) for e in entries))


if __name__ == "__main__":
    unittest.main()
