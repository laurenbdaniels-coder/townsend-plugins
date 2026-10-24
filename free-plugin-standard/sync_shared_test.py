"""sync_shared.py: copies shared/shared_rules.py into each plugin and stamps the shared markdown blocks (S-062).

Also the CI guard: no plugin keeps its own copy of a shared rule.

Run: python3 -m unittest discover -s free-plugin-standard -p '*_test.py' -v
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import sync_shared as ss  # noqa: E402

CANON = "free-plugin-standard/shared/shared_rules.py"
RUN = "run: python3 free-plugin-standard/sync_shared.py"


def fake_registry():
    return {
        "copies": ("alpha/scripts/shared_rules.py", "beta/scripts/shared_rules.py"),
        "blocks": {"mistake-meanings": ("alpha/assets/t.md", "beta/SKILL.md"),
                   "stopline-fields": ("beta/fields.md",)},
        "guarded": {"alpha": ("NEVER_OPEN_DIRS", "STOPLINE_FIELDS")},
        "excluded": (("alpha/scripts/frozen_*.py", "frozen release"), ("*/fixtures/*", "test inputs"),
                     ("*_test.py", "tests")),
    }


class FakeRepo(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sync-shared-")
        self.addCleanup(shutil.rmtree, self.root, True)
        os.makedirs(os.path.join(self.root, "free-plugin-standard", "shared"))
        shutil.copy(os.path.join(ROOT, CANON), os.path.join(self.root, CANON))
        self.canon = self.read(CANON)
        self.reg = fake_registry()
        self.write("alpha/scripts/shared_rules.py", self.canon)
        self.write("beta/scripts/shared_rules.py", self.canon)
        self.write("alpha/scripts/scan.py", "import os\nX = 1\n")
        body = ss.render_block(self.root, "mistake-meanings")
        self.write("alpha/assets/t.md", "Intro:\n    <!-- shared:mistake-meanings -->\n%s\n    <!-- /shared:mistake-meanings -->\nAfter.\n"
                   % "\n".join("    " + ln for ln in body.split("\n")))
        self.fields = ss.render_block(self.root, "stopline-fields")
        self.write("beta/SKILL.md", "Rule:\n  <!-- shared:mistake-meanings -->\n%s\n  <!-- /shared:mistake-meanings -->\n"
                   % "\n".join("  " + ln for ln in body.split("\n")))
        self.write("beta/fields.md", "Intro.\nFields such as <!-- shared:stopline-fields -->%s<!-- /shared:stopline-fields -->, too.\n"
                   % self.fields)

    def path(self, rel):
        return os.path.join(self.root, *rel.split("/"))

    def write(self, rel, text):
        p = self.path(rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8", newline="") as fh:
            return fh.read()

    def snapshot(self):
        out = {}
        for d, _dirs, files in os.walk(self.root):
            for f in files:
                with open(os.path.join(d, f), "rb") as fh:
                    out[os.path.relpath(os.path.join(d, f), self.root)] = fh.read()
        return out

    def check(self):
        return ss.check(self.root, self.reg)


class CheckTests(FakeRepo):
    def test_clean_repo_has_no_errors(self):
        self.assertEqual(self.check(), [])

    def test_stale_copy(self):
        self.write("beta/scripts/shared_rules.py", self.canon + "# drift\n")
        self.assertEqual(self.check(), ["stale-copy beta/scripts/shared_rules.py:1 block shared_rules: " + RUN])

    def test_missing_copy_is_stale(self):
        os.remove(self.path("alpha/scripts/shared_rules.py"))
        self.assertEqual(self.check(), ["stale-copy alpha/scripts/shared_rules.py:1 block shared_rules: " + RUN])

    def test_crlf_copy_is_stale(self):
        self.write("alpha/scripts/shared_rules.py", self.canon.replace("\n", "\r\n"))
        self.assertEqual(self.check(), ["stale-copy alpha/scripts/shared_rules.py:1 block shared_rules: " + RUN])

    def test_hand_edited_block(self):
        self.write("beta/SKILL.md", self.read("beta/SKILL.md").replace("card industry", "card-industry"))
        self.assertEqual(self.check(), [
            "hand-edited beta/SKILL.md:2 block mistake-meanings: %s (edit %s, not this block)" % (RUN, CANON)])

    def test_relative_indentation_counts(self):
        text = self.read("beta/SKILL.md").split("\n")
        text[3] = "  " + text[3]
        self.write("beta/SKILL.md", "\n".join(text))
        self.assertEqual(len(self.check()), 1)
        self.assertTrue(self.check()[0].startswith("hand-edited beta/SKILL.md:2 "))

    def test_missing_marker(self):
        self.write("beta/SKILL.md", "Rule: nothing here\n")
        self.assertEqual(self.check(), [
            "missing-marker beta/SKILL.md:1 block mistake-meanings: add <!-- shared:mistake-meanings -->…"
            "<!-- /shared:mistake-meanings --> in beta/SKILL.md"])

    def test_missing_target_file_is_a_missing_marker(self):
        os.remove(self.path("beta/SKILL.md"))
        self.assertEqual([e.split(" ")[0] for e in self.check()], ["missing-marker"])

    def test_unbalanced_marker(self):
        self.write("beta/SKILL.md", self.read("beta/SKILL.md").replace("  <!-- /shared:mistake-meanings -->\n", ""))
        self.assertEqual(self.check(), [
            "unbalanced-marker beta/SKILL.md:2 block mistake-meanings: give each <!-- shared:mistake-meanings --> "
            "one <!-- /shared:mistake-meanings --> after it in beta/SKILL.md"])

    def test_end_marker_without_start(self):
        self.write("beta/SKILL.md", "x\n<!-- /shared:mistake-meanings -->\n")
        self.assertEqual([e.split(" ")[:2] for e in self.check()],
                         [["unbalanced-marker", "beta/SKILL.md:2"]])

    def test_unregistered_block_name_in_a_target(self):
        self.write("beta/SKILL.md", self.read("beta/SKILL.md") + "<!-- shared:nope -->\n<!-- /shared:nope -->\n")
        errs = self.check()
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("unbalanced-marker beta/SKILL.md:"), errs)
        self.assertIn("block nope", errs[0])

    def test_hand_copy_of_a_guarded_name(self):
        self.write("alpha/scripts/scan.py", "import os\nNEVER_OPEN_DIRS = {'.claude'}\n")
        self.assertEqual(self.check(), [
            "hand-copy alpha/scripts/scan.py:2 block NEVER_OPEN_DIRS: delete the copy and use shared_rules, "
            "or add the path to EXCLUDED with a reason"])

    def test_hand_copy_forms(self):
        self.write("alpha/scripts/scan.py", "STOPLINE_FIELDS: tuple = ()\ndef NEVER_OPEN_DIRS():\n    pass\n")
        self.assertEqual([e.split(" ")[1] for e in self.check()],
                         ["alpha/scripts/scan.py:1", "alpha/scripts/scan.py:2"])

    def test_use_through_the_module_is_fine(self):
        self.write("alpha/scripts/scan.py", "def f(shared):\n    NEVER_OPEN_DIRS = 1\n    return shared.NEVER_OPEN_DIRS\n")
        self.assertEqual(self.check(), [])  # only top-level definitions are copies

    def test_copies_excluded_paths_and_unguarded_plugins_are_not_scanned(self):
        self.write("alpha/scripts/frozen_0_3_2.py", "NEVER_OPEN_DIRS = set()\n")
        self.write("alpha/scripts/fixtures/app/x.py", "NEVER_OPEN_DIRS = set()\n")
        self.write("alpha/scripts/scan_test.py", "NEVER_OPEN_DIRS = set()\n")
        self.write("beta/scripts/scan.py", "NEVER_OPEN_DIRS = set()\n")  # beta is not guarded yet
        self.assertEqual(self.check(), [])

    def test_unparseable_python_is_reported_not_crashed(self):
        self.write("alpha/scripts/scan.py", "def (:\n")
        errs = self.check()
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("hand-copy alpha/scripts/scan.py:"), errs)

    def test_lines_never_carry_matched_content(self):
        self.write("beta/SKILL.md", self.read("beta/SKILL.md").replace("card industry", "SECRET-TEXT"))
        self.write("alpha/scripts/scan.py", "NEVER_OPEN_DIRS = {'SECRET-TEXT'}\n")
        for line in self.check():
            self.assertNotIn("SECRET", line)


class InlineBlockTests(FakeRepo):
    def test_inline_block_renders_the_field_list(self):
        self.assertTrue(self.fields.startswith("`ssn`, `social_security`, "))
        self.assertTrue(self.fields.endswith("`birth_date`, `birthday`"))

    def test_inline_block_hand_edited(self):
        self.write("beta/fields.md", self.read("beta/fields.md").replace("`ssn`, ", ""))
        self.assertEqual(self.check(), [
            "hand-edited beta/fields.md:2 block stopline-fields: %s (edit %s, not this block)" % (RUN, CANON)])

    def test_inline_block_rewrite_keeps_the_rest_of_the_line(self):
        self.write("beta/fields.md", self.read("beta/fields.md").replace("`ssn`, ", ""))
        ss.rewrite(self.root, self.reg)
        self.assertIn("Fields such as <!-- shared:stopline-fields -->`ssn`, ", self.read("beta/fields.md"))
        self.assertIn("<!-- /shared:stopline-fields -->, too.\n", self.read("beta/fields.md"))
        self.assertEqual(self.check(), [])

    def test_inline_start_without_end_on_the_line(self):
        self.write("beta/fields.md", self.read("beta/fields.md").replace("<!-- /shared:stopline-fields -->", ""))
        self.assertEqual([e.split(" ")[:2] for e in self.check()], [["unbalanced-marker", "beta/fields.md:2"]])

    def test_never_open_renders_files_then_folders(self):
        text = ss.render_block(self.root, "never-open")
        self.assertTrue(text.startswith("instruction files (`CLAUDE.md`, `AGENTS.md`, "), text)
        self.assertIn("`.aider*`, and the folders `.claude/`, ", text)
        self.assertTrue(text.endswith("`.opencode/`)"), text)


class RewriteTests(FakeRepo):
    def test_rewrite_fixes_copies_and_blocks_and_is_idempotent(self):
        self.write("beta/scripts/shared_rules.py", "old\n")
        os.remove(self.path("alpha/scripts/shared_rules.py"))
        self.write("beta/SKILL.md", self.read("beta/SKILL.md").replace("card industry", "card-industry"))
        errors, written = ss.rewrite(self.root, self.reg)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(written), ["alpha/scripts/shared_rules.py", "beta/SKILL.md", "beta/scripts/shared_rules.py"])
        self.assertEqual(self.check(), [])
        before = self.snapshot()
        self.assertEqual(ss.rewrite(self.root, self.reg), ([], []))
        self.assertEqual(self.snapshot(), before)

    def test_rewrite_keeps_text_around_blocks_and_the_markers_indent(self):
        self.write("beta/SKILL.md", self.read("beta/SKILL.md").replace("card industry", "card-industry"))
        ss.rewrite(self.root, self.reg)
        text = self.read("beta/SKILL.md")
        self.assertTrue(text.startswith("Rule:\n  <!-- shared:mistake-meanings -->\n  - "))
        self.assertTrue(text.endswith("\n  <!-- /shared:mistake-meanings -->\n"))
        self.assertIn('card industry rules', text)

    def test_rewrite_writes_lf(self):
        self.write("beta/SKILL.md", self.read("beta/SKILL.md").replace("\n", "\r\n").replace("card industry", "x"))
        ss.rewrite(self.root, self.reg)
        self.assertNotIn("\r", self.read("beta/SKILL.md"))
        self.assertEqual(self.check(), [])

    def test_any_error_writes_nothing(self):
        self.write("beta/scripts/shared_rules.py", "old\n")
        self.write("alpha/assets/t.md", "no markers\n")
        before = self.snapshot()
        errors, written = ss.rewrite(self.root, self.reg)
        self.assertEqual(written, [])
        self.assertEqual([e.split(" ")[0] for e in errors], ["missing-marker"])
        self.assertEqual(self.snapshot(), before)

    def test_hand_copy_blocks_a_rewrite(self):
        self.write("beta/scripts/shared_rules.py", "old\n")
        self.write("alpha/scripts/scan.py", "NEVER_OPEN_DIRS = set()\n")
        before = self.snapshot()
        errors, written = ss.rewrite(self.root, self.reg)
        self.assertEqual((len(errors), written), (1, []))
        self.assertEqual(self.snapshot(), before)

    def test_no_temp_files_left(self):
        self.write("beta/scripts/shared_rules.py", "old\n")
        ss.rewrite(self.root, self.reg)
        self.assertEqual(sorted(os.listdir(self.path("beta/scripts"))), ["shared_rules.py"])


class CliTests(FakeRepo):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ss.main(list(argv), root=self.root, reg=self.reg)
        return code, out.getvalue(), err.getvalue()

    def test_clean_check_prints_nothing(self):
        self.assertEqual(self.run_main("--check"), (0, "", ""))

    def test_check_failure_is_one_line_per_error_on_stderr(self):
        self.write("beta/scripts/shared_rules.py", "old\n")
        code, out, err = self.run_main("--check")
        self.assertEqual((code, out), (1, ""))
        self.assertEqual(err, "stale-copy beta/scripts/shared_rules.py:1 block shared_rules: " + RUN + "\n")

    def test_rewrite_failure_says_nothing_was_written(self):
        self.write("alpha/assets/t.md", "no markers\n")
        code, _out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertTrue(err.endswith("side effects: none\n"), err)

    def test_rewrite_reports_written_files(self):
        self.write("beta/scripts/shared_rules.py", "old\n")
        code, out, err = self.run_main()
        self.assertEqual((code, out, err), (0, "wrote beta/scripts/shared_rules.py\n", ""))


class RealRepoTests(unittest.TestCase):
    def test_real_repo_is_in_sync(self):
        proc = subprocess.run([sys.executable, os.path.join(HERE, "sync_shared.py"), "--check"], cwd=ROOT,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, b"", b""))

    def test_every_registered_copy_is_byte_identical(self):
        with open(os.path.join(ROOT, CANON), "rb") as fh:
            canon = fh.read()
        self.assertTrue(ss.COPIES)
        for rel in ss.COPIES:
            with open(os.path.join(ROOT, rel), "rb") as fh:
                self.assertEqual(fh.read(), canon, rel)

    def test_registry_paths_exist(self):
        for rel in ss.COPIES + tuple(t for ts in ss.BLOCKS.values() for t in ts):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), rel)
        for plugin in ss.GUARDED:
            self.assertTrue(os.path.isdir(os.path.join(ROOT, plugin)), plugin)
            self.assertTrue(set(ss.GUARDED[plugin]) <= set(ss.GUARDED_NAMES), plugin)

    def test_frozen_release_is_excluded(self):
        self.assertTrue(ss.is_excluded("custody-check/skills/custody-check/scripts/custody_scan_0_3_2.py"))
        for rel in ("build-decisions/evals/x/case.py", "custody-check/skills/custody-check/scripts/fixtures/a/b.py",
                    "free-plugin-standard/corpus/x.py", "build-decisions/skills/build-decisions/scripts/census_scan_test.py"):
            self.assertTrue(ss.is_excluded(rel), rel)
        self.assertFalse(ss.is_excluded("build-decisions/skills/build-decisions/scripts/census_scan.py"))
        for _glob, reason in ss.EXCLUDED:
            self.assertTrue(reason.strip())

    def test_ci_runs_the_check(self):
        with open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8") as fh:
            self.assertIn("python3 free-plugin-standard/sync_shared.py --check", fh.read())


if __name__ == "__main__":
    unittest.main()
