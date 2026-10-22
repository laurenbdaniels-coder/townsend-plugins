"""The 0.6.0 report graders bite: they pass a hand-written 0.6.0 report and fail what they are there to stop.

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
DRAFT = os.path.join(HERE, "fixtures", "report", "seeded-app-0.6.0-hand-draft.md")
CORPUS = os.path.join(ROOT, "free-plugin-standard", "corpus", "build-decisions-reports.jsonl")

NEW_COMMON = ("footer-plain", "says-what-not-what-to-do", "never-asks-what-code-shows", "one-stopped-early-line")
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
        """protects=a correct 0.6.0 report passes its own case; fails_when=a grader pins a line 0.6.0 removed."""
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
        for name in ("never-asks-what-code-shows", "one-stopped-early-line"):
            self.assertFalse(fails(self.g[name], old), name)

    def test_one_minute_test_after_the_footer_is_allowed(self):
        """The chat-only test after the footer may say "ask your AI tool"; only the report above it is graded."""
        text = draft() + 'Test: "Ask your AI tool where your app decides one price."\n'
        self.assertFalse(fails(self.g["says-what-not-what-to-do"], text))


class AllCasesTests(unittest.TestCase):
    def test_every_rendering_case_carries_the_plain_report_graders(self):
        try:
            import yaml
        except ImportError:
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
                for name in NEW_COMMON:
                    self.assertIn(name, names, (case, name))
                with open(path, encoding="utf-8") as fh:
                    footer = [g for g in yaml.safe_load(fh)["graders"] if g["name"] == "footer-plain"][0]["pattern"]
                self.assertEqual(footer, FOOTER, case)
                for gone in ("before-you-change", "points-to-custody-check", "by-hand-checks", "get-a-person",
                             "asks-which-copy-is-real", "points-to-assessment-for-the-fix", "std-check-it"):
                    self.assertNotIn(gone, names, (case, gone))


if __name__ == "__main__":
    unittest.main()
