"""build-decisions 0.6.0 follows SCOPE.md: the shipped text never tells the founder what to do.

SCOPE.md (free-plugin-standard/SCOPE.md) says that from 0.6.0 build-decisions prints what is broken and what it
means, nothing to do, no link and no pointer to the other plugin. These tests read the shipped files, not a
model's output; the eval graders check real reports.

Run: python3 -m unittest discover -s build-decisions/skills/build-decisions/scripts -p '*_test.py' -v
"""
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
PLUGIN = os.path.dirname(os.path.dirname(SKILL_DIR))
ROOT = os.path.dirname(PLUGIN)

# Exact, case-sensitive strings 0.5.1 printed and SCOPE.md bans from 0.6.0.
BANNED = ("Check it", "Before you change", "Free Assessment", "assessment?src", "run custody-check",
          "Custody Check answers", "get a person", "Next:", "check by hand", "one-minute check")
MARKER = "<!-- scope-list -->"

# The S5 one-minute tests, asked in the chat only, never in the report.
SIGN_TESTS = (
    "Pick one thing you fixed. Open the screen where it broke and do the same steps again.",
    "Think of your last change. Open two screens it did not mean to touch and press their main button.",
    "Ask your AI tool where your app decides one price. See if it names one place, or several.",
    "Open two screens that show the same price or plan. Compare what they say.",
)

# The report's order, top to bottom (plan A1). The README example and the template follow it.
ORDER = ("# Build decisions:", "**Your app has", "Why this matters", "We read", "How your app is built",
         "**1.", "Also worth a look", "Not checked", "\n---\n", "build-decisions v")


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def skill():
    return read(SKILL_DIR, "SKILL.md")


def template(text):
    """The Step 5 report template: the first ```markdown fence after '## Step 5'."""
    step5 = text[text.index("## Step 5"):]
    start = step5.index("```markdown")
    return step5[start:step5.index("\n```\n", start + 1)]


# A pointer to the other plugin is banned in any letter case ("Run custody-check", "run custody-check").
BANNED_ANY_CASE = ("run custody-check",)


def found(text, skip=lambda line: False):
    out = []
    for line in text.splitlines():
        if skip(line):
            continue
        out += [(s, line) for s in BANNED if s in line]
        out += [(s, line) for s in BANNED_ANY_CASE if s in line.lower() and s not in line]
    return out


class SkillTextTests(unittest.TestCase):
    def test_skill_has_no_banned_line(self):
        """protects=no 0.5.1 do-this line in the instructions the model copies; fails_when=any banned string is
        put back outside the one scope-list line; no_claim=the model's own wording (eval graders)."""
        self.assertEqual(found(skill(), skip=lambda line: MARKER in line), [])

    def test_one_scope_list_line(self):
        self.assertEqual(sum(MARKER in line for line in skill().splitlines()), 1)

    def test_template_never_says_change_nothing(self):
        self.assertNotIn("Change nothing", template(skill()))

    def test_template_follows_the_report_order(self):
        tpl = template(skill())
        at = [tpl.find(s.replace("**1.", "**<n>.")) for s in ORDER]
        self.assertNotIn(-1, at, dict(zip(ORDER, at)))
        self.assertEqual(at, sorted(at))

    def test_one_minute_tests_only_in_the_questions(self):
        text, tpl = skill(), template(skill())
        for t in SIGN_TESTS:
            self.assertIn(t, text)
            self.assertNotIn(t, tpl)

    def test_coverage_forms_match_the_shared_grader(self):
        """protects=the template's three coverage lines pass the pack's std-coverage-line; fails_when=one is reworded."""
        pack = json.loads(read(ROOT, "free-plugin-standard", "pack.json"))
        pattern = [g for g in pack["groups"]["always"] if g["name"] == "std-coverage-line"][0]["pattern"]
        forms = re.findall(r'^- the census[^:]*: "(We read [^"]+)"', skill(), re.M)
        self.assertEqual(len(forms), 3, forms)
        for form in forms:
            line = re.sub(r"<[nm]>", "7", form)
            self.assertRegex("\n" + line, pattern, form)

    def test_the_pattern_bites(self):
        for line in ("Check it (1 min): open the page.", "**Before you change any of these:** ask",
                     "townsendaistudio.com/assessment?src=build-decisions", "For keys, run custody-check.",
                     "Run custody-check next."):
            self.assertTrue(found(line), line)


class ShippedCopyTests(unittest.TestCase):
    def descriptions(self):
        plugin = json.loads(read(PLUGIN, ".claude-plugin", "plugin.json"))["description"]
        market = json.loads(read(ROOT, ".claude-plugin", "marketplace.json"))
        entry = [p for p in market["plugins"] if p["name"] == "build-decisions"][0]["description"]
        desc = skill().split("\n---\n", 1)[0]
        return {"plugin.json": plugin, "marketplace.json": entry, "SKILL.md description": desc}

    def test_descriptions_have_no_banned_line(self):
        for name, text in self.descriptions().items():
            self.assertEqual(found(text), [], name)
            self.assertNotIn("which door", text, name)

    def test_root_readme_row(self):
        rows = [l for l in read(ROOT, "README.md").splitlines() if l.startswith("| build-decisions |")]
        self.assertEqual(len(rows), 1)
        self.assertEqual(found(rows[0]), [])

    def test_plugin_readme(self):
        text = read(PLUGIN, "README.md")
        # SCOPE.md: the README may carry the Free Assessment link; that line alone is exempt.
        self.assertEqual(found(text, skip=lambda line: "townsendaistudio.com/assessment" in line), [])
        self.assertNotIn("which door", text)

    def test_readme_example_follows_the_report_order(self):
        text = read(PLUGIN, "README.md")
        start = text.index("# Build decisions:")
        example = text[start:text.index("```", start)]
        at = [example.find(s) for s in ORDER]
        self.assertNotIn(-1, at, dict(zip(ORDER, at)))
        self.assertEqual(at, sorted(at))
        self.assertIn(": the browser chooses it.**", example)

    def test_standard_has_no_banned_line(self):
        self.assertEqual(found(read(ROOT, "free-plugin-standard", "STANDARD.md")), [])


# Kinds of warning the 0.7.0 sample cut or deferred (S-059): no shipped description or trigger may name them.
CUT_KINDS = re.compile(r"never runs|dead code|unused|does not use|more parts than|not use", re.I)
ADVICE = re.compile(r"\byou should\b|\bremove\b|\bdelete\b|\bpick one\b|\bkeep one\b|\bswitch to\b|\breplace\b",
                    re.I)


class WarningsCopyTests(unittest.TestCase):
    descriptions = ShippedCopyTests.descriptions

    def test_descriptions_name_only_the_shipped_kind(self):
        """protects=D7: the shipped copy names only the warning that passed its sample;
        fails_when=a description names a cut kind, or drops the shipped one;
        no_claim=the README's Not yet column, which lists what is not checked."""
        for name, text in self.descriptions().items():
            self.assertIsNone(CUT_KINDS.search(text), name)
            self.assertRegex(text, r"two or more libraries|two libraries for the same thing", name)
        self.assertIn('"does my app use two libraries for the same thing"', self.descriptions()["SKILL.md description"])
        self.assertNotIn("dead code", skill())

    def test_how_it_decides_gives_no_advice(self):
        """protects=X9: the README says how a warning is decided and never what to change;
        fails_when=the entry is missing, names a cut kind, or gives advice;
        no_claim=the report itself (evals)."""
        text = read(PLUGIN, "README.md")
        part = text.split("## How Build Decisions decides a warning", 1)[1].split("\n## ", 1)[0]
        self.assertIn("One job done in more than one way", part)
        self.assertIsNone(CUT_KINDS.search(part))
        self.assertIsNone(ADVICE.search(part))


class VersionTests(unittest.TestCase):
    def test_one_version_everywhere(self):
        """protects=the footer, manifests and docs name one release; fails_when=any of the five places is
        left behind."""
        helper = re.search(r'^__version__ = "([^"]+)"', read(HERE, "census_scan.py"), re.M).group(1)
        plugin = json.loads(read(PLUGIN, ".claude-plugin", "plugin.json"))["version"]
        market = [p for p in json.loads(read(ROOT, ".claude-plugin", "marketplace.json"))["plugins"]
                  if p["name"] == "build-decisions"][0]["version"]
        changelog = re.search(r"^## \[?(\d+\.\d+\.\d+)", read(PLUGIN, "CHANGELOG.md"), re.M).group(1)
        row = [l for l in read(ROOT, "README.md").splitlines() if l.startswith("| build-decisions |")][0]
        readme = row.split("|")[2].strip()
        self.assertEqual({helper, plugin, market, changelog, readme}, {helper}, (helper, plugin, market, changelog, readme))
        self.assertEqual(helper, "0.7.0")


if __name__ == "__main__":
    unittest.main()
