"""The 0.6.x report graders bite: they pass a hand-written 0.6.1 report and fail what they are there to stop.

Each new grader passes the hand draft (fixtures/report/), fails a targeted bad example, and fails the saved 0.5.1
seeded-app report only where that report really breaks the new rule (plan D17). Needs PyYAML (CI installs it).

Run: python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p '*_test.py' -v
"""
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
ROOT = os.path.dirname(PLUGIN)
DRAFT = os.path.join(HERE, "fixtures", "report", "seeded-app-0.6.1-hand-draft.md")
CORPUS = os.path.join(ROOT, "free-plugin-standard", "corpus", "build-decisions-reports.jsonl")

NEW_COMMON = ("footer-plain", "says-what-not-what-to-do", "never-asks-what-code-shows", "one-stopped-early-line",
              "one-sign-at-a-time", "nothing-of-the-report-after-footer")
# 0.6.1: the eval host has no AskUserQuestion, so a case the code does not tick asks the stop-line question in
# plain text right after the footer, then waits. A case the code ticks (stopline-app) never asks it.
ASKS_AFTER = ("stopline-question-after-footer", "waits-after-stopline-question")
TICKED = {"stopline-app": ("first-sign-after-footer", "no-stopline-question")}
# New in 0.6.0 that a saved 0.5.1 seeded-app report really breaks (it had the old footer, a check line, the old
# label and no coverage line). The other new graders guard things 0.5.1 already did right.
OLD_REPORT_BREAKS = ("footer-plain", "says-what-not-what-to-do", "what-it-means-per-block", "std-coverage-line",
                     "std-out-of-sync")

FOOTER = "\\n---\\nbuild-decisions v\\d+\\.\\d+\\.\\d+ · read-only · a review, not an audit"

BAD = {
    "footer-plain": "# Build decisions: x\n\n---\nbuild-decisions v0.6.0 · 16 files · 17 searches and reads · read-only · a review, not an audit\n",
    "says-what-not-what-to-do": "# Build decisions: x\n\nCheck it (1 min): open the page.\n\n---\nbuild-decisions v0.6.0 · read-only · a review, not an audit\n",
    "never-asks-what-code-shows": "# Build decisions: x\n\nWho can read your customers' records?\n",
    "one-stopped-early-line": "The scan stopped early: it reached its file limit.\nThe scan stopped early, so there may be more.\n",
    "what-it-means-per-block": "**1. A**\nWhat it means for you: x.\n**2. B**\nWhat it means for you: y.\n",
    # 0.6.0's ending: the first sign straight after the footer, with no stop-line question.
    "stopline-question-after-footer": ("# Build decisions: x\n\n---\nbuild-decisions v0.6.0 \u00b7 read-only \u00b7 a review, "
                                       "not an audit\n\nFirst, a question: did a fix ever not take? Pick one thing you fixed.\n"),
    "waits-after-stopline-question": ("# Build decisions: x\n\n---\nbuild-decisions v0.6.1 \u00b7 read-only \u00b7 a review, "
                                      "not an audit\n\nDoes this app do any of these? Store or handle card details itself.\n\n"
                                      "First, a question: did a fix ever not take? Pick one thing you fixed.\n"),
    "no-did-not-ask-line": ("Not checked: the rest.\nThis run did not ask whether your app handles card details, other "
                            "people's money or sensitive data.\n"),
    "one-sign-at-a-time": ("# Build decisions: x\n\n---\nbuild-decisions v0.6.0 \u00b7 read-only \u00b7 a review, not an audit\n"
                           "1. Pick one thing you fixed.\n2. Open two screens it did not mean to touch.\n"),
    "nothing-of-the-report-after-footer": ("# Build decisions: x\n\n---\nbuild-decisions v0.6.0 \u00b7 read-only \u00b7 a "
                                           "review, not an audit\nNot checked: the rest.\nPick one thing you fixed.\n"),
}


def graders(case):
    import yaml
    with open(os.path.join(PLUGIN, "evals", case, "case.yaml"), encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return {g["name"]: (g["pattern"], g.get("flags", ""), g["match"]) for g in doc["graders"] if g.get("type") == "regex"}


def fails(check, text):
    pattern, flags, match = check
    hit = re.search(pattern, text, re.I if "i" in flags else 0) is not None
    return hit if match == "not_contains" else not hit


def draft():
    with open(DRAFT, encoding="utf-8") as fh:
        return fh.read()


def old_report():
    with open(CORPUS, encoding="utf-8") as fh:
        rows = [json.loads(l) for l in fh]
    return [r["text"] for r in rows if r["case"] == "seeded-app" and r["version"] == "0.5.1"][0]


class SeededAppGraderTests(unittest.TestCase):
    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            if os.environ.get("CI"):
                raise
            self.skipTest("PyYAML not installed (CI installs it)")
        self.g = graders("seeded-app")

    def test_every_regex_grader_passes_the_hand_draft(self):
        """protects=a correct 0.6.1 report passes its own case; fails_when=a grader pins a line 0.6.x removed."""
        failing = [n for n, c in self.g.items() if fails(c, draft())]
        self.assertEqual(failing, [])

    def test_each_new_grader_bites(self):
        for name, bad in BAD.items():
            self.assertIn(name, self.g, name)
            self.assertTrue(fails(self.g[name], bad), name)

    def test_the_old_report_fails_only_where_it_breaks_the_rule(self):
        old = old_report()
        for name in OLD_REPORT_BREAKS:
            self.assertTrue(fails(self.g[name], old), name)
        for name in ("never-asks-what-code-shows", "one-stopped-early-line", "one-sign-at-a-time",
                     "nothing-of-the-report-after-footer", "stopline-question-after-footer",
                     "waits-after-stopline-question", "no-did-not-ask-line"):
            self.assertFalse(fails(self.g[name], old), name)

    def test_one_minute_test_after_the_footer_is_allowed(self):
        """The chat-only test after the footer may say "ask your AI tool"; only the report above it is graded."""
        text = draft() + 'Test: "Ask your AI tool where your app decides one price."\n'
        self.assertFalse(fails(self.g["says-what-not-what-to-do"], text))


class StoplineAppGraderTests(unittest.TestCase):
    """protects=the stop-line app, whose code already answers the stop-line question, never asks it after the
    footer and goes straight to the first sign; fails_when=no-stopline-question's pattern stops matching the
    question (a typo), so a run that asks it anyway passes."""

    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            if os.environ.get("CI"):
                raise
            self.skipTest("PyYAML not installed (CI installs it)")
        self.g = graders("stopline-app")

    def test_no_stopline_question_bites(self):
        footer = "# Build decisions: x\n\n---\nbuild-decisions v0.6.1 \u00b7 read-only \u00b7 a review, not an audit\n\n"
        asks = footer + "Does this app do any of these? Store or handle card details itself.\n"
        signs = footer + "First, a question: did a fix ever not take? Pick one thing you fixed.\n"
        self.assertTrue(fails(self.g["no-stopline-question"], asks))
        self.assertFalse(fails(self.g["no-stopline-question"], signs))
        self.assertFalse(fails(self.g["first-sign-after-footer"], signs))
        self.assertTrue(fails(self.g["first-sign-after-footer"], asks))


class AllCasesTests(unittest.TestCase):
    def test_every_rendering_case_carries_the_plain_report_graders(self):
        try:
            import yaml
        except ImportError:
            if os.environ.get("CI"):
                raise
            self.skipTest("PyYAML not installed (CI installs it)")
        with open(os.path.join(ROOT, "free-plugin-standard", "pack.json"), encoding="utf-8") as fh:
            exempt = json.load(fh)["plugins"]["build-decisions"]["exempt"]
        for root in ("evals", "evals-no-search"):
            for case in sorted(os.listdir(os.path.join(PLUGIN, root))):
                path = os.path.join(PLUGIN, root, case, "case.yaml")
                if case in exempt or not os.path.isfile(path):
                    continue
                with open(path, encoding="utf-8") as fh:
                    names = {g["name"] for g in yaml.safe_load(fh)["graders"]}
                for name in NEW_COMMON + TICKED.get(case, ASKS_AFTER):
                    self.assertIn(name, names, (case, name))
                if case not in TICKED:
                    # 0.6.0's "first sign comes right after the footer" no longer holds: the question comes first.
                    self.assertNotIn("first-sign-after-footer", names, case)
                    self.assertNotIn("did-not-ask-line", names, case)
                with open(path, encoding="utf-8") as fh:
                    footer = [g for g in yaml.safe_load(fh)["graders"] if g["name"] == "footer-plain"][0]["pattern"]
                self.assertEqual(footer, FOOTER, case)
                for gone in ("before-you-change", "points-to-custody-check", "by-hand-checks", "get-a-person",
                             "asks-which-copy-is-real", "points-to-assessment-for-the-fix", "std-check-it"):
                    self.assertNotIn(gone, names, (case, gone))



class ReadLimitGraderTests(unittest.TestCase):
    """protects=Reads stay at 120 lines except whole reads (limit 401) of the server files the helper lists for
    that case's app (plan S35, EV12); fails_when=a 401-line read of any other file passes, a listed-file read
    above 401 passes, or a case's grader is stale against what the helper lists today."""

    def setUp(self):
        try:
            import yaml
        except ImportError:
            if os.environ.get("CI"):
                raise
            self.skipTest("PyYAML not installed (CI installs it)")
        with open(os.path.join(PLUGIN, "evals", "browser-decides", "case.yaml"), encoding="utf-8") as fh:
            g = {x["name"]: x.get("input_match") for x in yaml.safe_load(fh)["graders"] if x.get("type") == "tool_used"}
        self.at_120, self.at_401 = g["read-at-most-120-lines"], g["read-at-most-401-lines"]

    def hit(self, pattern, path, limit):
        return re.search(pattern, json.dumps({"file_path": path, "offset": 1, "limit": limit})) is not None

    def test_whole_reads_only_of_listed_server_files(self):
        for rel in ("app/api/coach/route.ts", "app/actions/award.ts", "app/settings/actions.ts"):
            path = "/private/tmp/e-x/home/cwd/nightowl/" + rel
            self.assertFalse(self.hit(self.at_120, path, 401), rel)
            self.assertTrue(self.hit(self.at_401, path, 402), rel)
        for rel in ("components/Award.tsx", "lib/db.ts", "app/api/other/route.ts"):
            self.assertTrue(self.hit(self.at_120, "/private/tmp/e-x/home/cwd/nightowl/" + rel, 401), rel)
        self.assertTrue(self.hit(self.at_120, "/t/nightowl/app/api/coach/route.ts", 200))
        self.assertFalse(self.hit(self.at_120, "/t/nightowl/components/Award.tsx", 120))

    def test_every_case_is_stamped_from_the_helper(self):
        import subprocess
        import sys
        tool = os.path.join(PLUGIN, "evals", "whole_read_paths.py")
        proc = subprocess.run([sys.executable, tool], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout[-500:])

    def test_a_stale_case_fails_the_stamp_check(self):
        """protects=CI goes red when a case's 401-line grader no longer matches what the helper lists;
        fails_when=whole_read_paths.py stops returning 1 on a stale case, so the check above passes anyway."""
        import shutil
        import subprocess
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            copy = os.path.join(tmp, "build-decisions")
            shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns("results", "__pycache__"))
            case = os.path.join(copy, "evals", "browser-decides", "case.yaml")
            with open(case, encoding="utf-8") as fh:
                text = fh.read()
            stale = text.replace("app/api/coach/route\\\\.ts", "app/api/gone/route\\\\.ts")
            self.assertNotEqual(stale, text)
            with open(case, "w", encoding="utf-8") as fh:
                fh.write(stale)
            proc = subprocess.run([sys.executable, os.path.join(copy, "evals", "whole_read_paths.py")],
                                  capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stdout[-500:])
        self.assertIn("stale: browser-decides", proc.stdout)


class CaseAppNameTests(unittest.TestCase):
    def test_path_graders_name_the_case_own_app(self):
        """protects=a case's stays-in-app graders name the folder its prompt runs on; fails_when=a case copied
        from another keeps that case's folder name, so every Read of the real app counts as outside it."""
        try:
            import yaml
        except ImportError:
            if os.environ.get("CI"):
                raise
            self.skipTest("PyYAML not installed (CI installs it)")
        fixtures = set(os.listdir(os.path.join(PLUGIN, "evals", "fixtures")))
        for root in ("evals", "evals-no-search"):
            for case in sorted(os.listdir(os.path.join(PLUGIN, root))):
                path = os.path.join(PLUGIN, root, case, "case.yaml")
                if not os.path.isfile(path):
                    continue
                with open(path, encoding="utf-8") as fh:
                    doc = yaml.safe_load(fh)
                m = re.search(r"\./([A-Za-z0-9_-]+)", doc["execution"]["prompt"])
                if not m:
                    continue
                app = m.group(1)
                for g in doc["graders"]:
                    text = str(g.get("input_match", ""))
                    for other in fixtures - {app}:
                        self.assertNotIn("/%s/" % other, text, (case, g["name"], other))


if __name__ == "__main__":
    unittest.main()
