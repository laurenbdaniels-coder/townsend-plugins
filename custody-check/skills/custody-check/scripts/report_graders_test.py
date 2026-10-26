"""The eval cases' report graders, checked on known reports before an eval run relies on them (E-P3-13).

0.6.0's plain report (plan 1e, amended by 1f): every regex grader of the seeded-app case, its shared
free-plugin-standard block included, must pass the amended hand draft that Lauren approved. Every grader 0.6.0
adds or rewords must fail at least one saved 0.5.0 seeded-app report, so it catches the old shape (and its
NEW_GRADERS entry stays needed). Standard library only: the custody CI job has no YAML parser, and the case files
write every grader field as a JSON string or number.

Run from this folder: python3 -m unittest report_graders_test
"""
import json
import os
import re
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
REPO_ROOT = os.path.dirname(PLUGIN_DIR)
DRAFT = os.path.join(SCRIPT_DIR, "fixtures", "report", "seeded-app-0.6.0-hand-draft.md")
CORPUS = os.path.join(REPO_ROOT, "free-plugin-standard", "corpus", "custody-check-reports.jsonl")

# Added or reworded in 0.6.0 (the shared ones in custody-check's own words).
NEW_IN_0_6_0 = ("std-coverage-line", "no-workshop-words", "says-what-not-what-to-do", "no-five", "never-all-clear",
                "extra-risk-block", "do-today-before-problems", "first-screen-short", "report-at-most-500-words",
                "not-checked-line", "std-count-line", "std-out-of-sync")


def regex_graders(case):
    """{name: (pattern, flags, match)} for the case's regex graders, read line by line."""
    with open(os.path.join(PLUGIN_DIR, "evals", case, "case.yaml"), encoding="utf-8") as fh:
        text = fh.read()
    out = {}
    for item in re.split(r"(?m)^  - name: ", text)[1:]:
        fields = dict(re.findall(r"(?m)^    (\w+): (.+)$", item))
        if fields.get("type") != '"regex"':
            continue
        name = json.loads(item.split("\n", 1)[0])
        out[name] = (json.loads(fields["pattern"]), json.loads(fields["flags"]), json.loads(fields["match"]))
    return out


def fails(check, text):
    pattern, flags, match = check
    found = re.search(pattern, text, re.I if "i" in flags else 0) is not None
    return found if match == "not_contains" else not found


def saved(case, version):
    with open(CORPUS, encoding="utf-8") as fh:
        return [r["text"] for r in map(json.loads, fh) if r["case"] == case and r["version"] == version]


class SeededAppGraderTests(unittest.TestCase):
    def setUp(self):
        self.graders = regex_graders("seeded-app")
        with open(DRAFT, encoding="utf-8") as fh:
            self.draft = fh.read()

    def test_the_reader_sees_the_graders_the_runner_sees(self):
        """The line reader must find every regex grader, shared block included."""
        self.assertEqual(len(self.graders), 18)  # 13 of its own + 5 shared
        for name in NEW_IN_0_6_0 + ("std-no-fix-prompt", "std-no-code-words", "std-why-it-matters"):
            self.assertIn(name, self.graders)
        self.assertNotIn("std-check-it", self.graders, "custody-check omits Check it (pack.json)")

    def test_every_grader_passes_the_approved_draft(self):
        for name, check in sorted(self.graders.items()):
            self.assertFalse(fails(check, self.draft), name)

    def test_every_new_grader_fails_an_old_report(self):
        old = saved("seeded-app", "0.5.0")
        self.assertTrue(old, "no saved 0.5.0 seeded-app report")
        for name in NEW_IN_0_6_0:
            if name == "never-all-clear":
                continue  # 0.5.0 never printed the all-clear line either; it guards new reports only
            self.assertTrue(any(fails(self.graders[name], t) for t in old), name)

    def test_word_budgets_bite(self):
        """Mutation check: a long report and a long first screen fail."""
        filler = " ".join(["word"] * 200)
        longer = self.draft.replace("Why this matters:", filler + "\nWhy this matters:", 1)
        self.assertTrue(fails(self.graders["first-screen-short"], longer))
        self.assertTrue(fails(self.graders["report-at-most-500-words"], self.draft + filler))
        self.assertFalse(fails(self.graders["report-at-most-500-words"], self.draft))

    def test_says_what_not_what_to_do_bites(self):
        for line in ("Check it (1 min): ask your AI tool: \"x. Change nothing.\"",
                     "**Our advice: get an expert to look before your next change.**",
                     "**Before you change any of these:** ask your AI tool.",
                     "For a rule your app decides in more than one place, run build-decisions."):
            self.assertTrue(fails(self.graders["says-what-not-what-to-do"], self.draft + "\n" + line), line)

    def test_no_workshop_words_bites(self):
        for line in ("## Door: **Get a person**", "## The eleven", "Q4 is open.", "The stop-line is ticked.",
                     "This change is Gated."):
            self.assertTrue(fails(self.graders["no-workshop-words"], self.draft + "\n" + line), line)

    def test_never_all_clear_bites(self):
        line = "**We found no problems in your code, and your code and your answers settled every question we ask.**"
        self.assertTrue(fails(self.graders["never-all-clear"], self.draft + "\n" + line))

    def test_count_line_forms_all_pass(self):
        check = self.graders["std-count-line"]
        for line in ("**We found 1 problem in your code, and 1 thing your code can't tell us.**",
                     "**We found 2 problems in your code, and nothing else your code can't tell us.**",
                     "**We found no problems in your code, and 3 things your code can't tell us.**",
                     "**We found no problems in your code, and your code and your answers settled every question we ask.**"):
            self.assertFalse(fails(check, "# Custody check: x\n\n" + line + "\n"), line)


class AllCasesTests(unittest.TestCase):
    CASES = ("fix-request", "handlers-checked", "handlers-unchecked", "hostile-repo", "seeded-app", "symlinked-app")

    def test_every_case_carries_the_plain_report_graders(self):
        for case in self.CASES:
            g = regex_graders(case)
            for name in ("std-coverage-line", "no-workshop-words", "says-what-not-what-to-do", "no-five", "not-checked-line"):
                self.assertIn(name, g, "%s: %s" % (case, name))
            for gone in ("renders-the-eleven", "door-patch-it", "door-ship-it", "before-you-change-line",
                         "points-to-build-decisions", "one-place-line", "never-ship-it", "std-check-it"):
                self.assertNotIn(gone, g, "%s: %s" % (case, gone))

    def test_four_shell_commands_the_inventory_and_the_slice_plan(self):
        # 0.7.0 (S-068): the full read adds full_read_slices.py, so three became four.
        for case in self.CASES:
            with open(os.path.join(PLUGIN_DIR, "evals", case, "case.yaml"), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn('- name: "four-shell-commands"', text, case)
            self.assertIn('- name: "inventory-ran-once"', text, case)
            self.assertRegex(text, r'- name: "slice-plan-(?:ran|at-most)-once"', case)
            self.assertIn('"Agent"', text, case)
            self.assertNotIn('- name: "three-shell-commands"', text, case)
            scan = re.search(r'- name: "scanner-ran-once"\n(?:    .+\n)+', text).group(0)
            pat = json.loads(re.search(r"input_match: (.+)", scan).group(1))
            self.assertTrue(re.search(pat, "python3 -I '/p/custody_scan.py' --repo 'tasklane' 2>/dev/null"), case)
            self.assertFalse(re.search(pat, "python3 -I '/p/custody_scan.py' --inventory --repo 'tasklane'"), case)


if __name__ == "__main__":
    unittest.main()
