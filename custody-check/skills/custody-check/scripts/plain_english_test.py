"""Plain English for what the founder reads (0.3.6, after Matt Pocock's /wait-what, MIT, as decision-census 0.1.2).

What a founder reads: the verdict template's markdown block, the footer and partial-reason lines, the fixed lines
SKILL.md tells the agent to say, and the by-hand tests and fixes in references/questions.md. No sentence there runs
over 25 words, and no instruction (a by-hand step, a fix) over 20. The verdict opens with one line of context.

The door must not move: SKILL.md's `## Door rule`, the scanners and the verdict script (except `__version__`) are
byte-identical to the release this branch left (custody_scan_test._release_ref).

Run from this folder: python3 -m unittest plain_english_test
"""
import os
import re
import subprocess
import unittest

import custody_scan_test as cst

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SKILL_DIR)))
LONG = re.compile(r"(?:[^\s.!?|\n]+[ \t]+){25,}[^\s.!?|\n]+")  # 26+ words with no . ! ? or | between them


def read(*parts):
    with open(os.path.join(SKILL_DIR, *parts), encoding="utf-8") as fh:
        return fh.read()


def plain(text):
    """Code spans count as one word; placeholders and markdown emphasis drop out."""
    text = re.sub(r"`[^`]*`", "CODE", text)
    text = re.sub(r"<[^>\n]*>", "", text)
    return text.replace("**", "").replace("*", "")


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|(?<=[.!?]\")\s+|\n+", plain(text)) if s.strip()]


def words(sentence):
    return len(sentence.split())


def template_block():
    return read("assets", "verdict-template.md").split("```markdown", 1)[1].split("```", 1)[0]


def quoted_lines(text):
    """Fixed lines in quotes the agent copies to the founder (footer, partial reasons, said-in-one-sentence lines).
    SKILL.md's front matter is the host's trigger text, not the founder's, so it is left out."""
    if text.startswith("---\n"):
        text = text.split("\n---\n", 1)[1]
    return [q for q in re.findall(r'"([^"\n]{40,})"', text)]


# The lines SKILL.md tells the agent to say to the founder, word for word. Each pattern must still match.
SKILL_FOUNDER = (
    r'say so in one sentence \("([^"]+)"\)',              # the scanner could not run
    r'say so in one sentence: "([^"]+)"',                   # the verdict script could not run
    r'ask the stop-line as "([^"]+)"',
    r'ask one question: "([^"]+)"',                         # the money follow-up
    r'So \*\*ask\*\*: "([^"]+)"',                          # does your app call an AI model?
    r'"(your package file[^"]+)"',
    r'"(do you train[^"]+)"',
    r"^> (.+)$",                                            # the preflight message
)


def skill_founder_lines():
    text = read("SKILL.md")
    out = []
    for pat in SKILL_FOUNDER:
        found = re.findall(pat, text, re.M)
        assert found, "SKILL.md no longer has the founder line " + pat
        out += found
    return out


def by_hand_blocks():
    """Each `**By hand …:**` and `**The fix:**` bullet (with its numbered sub-steps) in questions.md."""
    out = []
    for m in re.finditer(r"^- \*\*(By hand[^*]*|The fix):\*\*(.*?)(?=^- |^#+ |\Z)", read("references", "questions.md"),
                         re.M | re.S):
        out.append((m.group(1), m.group(2)))
    return out


class FounderTextTests(unittest.TestCase):
    def test_template_block_has_no_sentence_over_25_words(self):
        for line in template_block().splitlines():
            if line.startswith("|") or not line.strip():
                continue
            self.assertNotRegex(plain(line), LONG, line)

    def test_fixed_quoted_lines_have_no_sentence_over_25_words(self):
        for q in quoted_lines(read("assets", "verdict-template.md")) + skill_founder_lines():
            for s in sentences(q):
                self.assertLessEqual(words(s), 25, s)

    def test_by_hand_steps_and_fixes_are_at_most_20_words_a_sentence(self):
        blocks = by_hand_blocks()
        self.assertGreaterEqual(len(blocks), 17, "Q1-Q11 and A1-A6 each have a by-hand test")
        for head, body in blocks:
            for s in sentences(body):
                self.assertLessEqual(words(s), 20, "%s: %s" % (head, s))

    def test_context_line_comes_first(self):
        block = template_block()
        head = block.split("## Stop-line", 1)[0]
        self.assertRegex(head, r"(?i)this check reads your app's files")
        self.assertRegex(head, r"(?i)\bdoor\b")

    def test_the_rules_catch_long_text(self):
        """Round 1: a semicolon or a colon is not a sentence break, so neither can hide a long sentence."""
        long_steps = ("Run the command in the app folder; check every line it prints carefully; and if a file looks odd, "
                      "open it and read it slowly.")
        self.assertGreater(max(words(s) for s in sentences(long_steps)), 20)
        self.assertRegex(plain("These are not failures: each of them is simply a question that you have not yet answered: "
                               "about the app, its data, its users and its money, and nothing more."), LONG)

    def test_by_hand_tests_keep_their_steps(self):
        """Round 1: the rewrite must not drop a way to run a test."""
        q = read("references", "questions.md")
        self.assertRegex(q, r"in the URL or the request")
        q4 = q.split("## Q4.", 1)[1].split("## Q5.", 1)[0]
        self.assertLess(q4.index("copy"), q4.index("ordinary user"), "copy the request as the owner first")
        self.assertIn("not summarised", q)

    def test_copy_exactly_text_is_exempt(self):
        section = read("SKILL.md").split("## Plain English", 1)[1].split("\n## ", 1)[0]
        self.assertRegex(section, r"(?i)copy exactly.*stays as written")

    def test_skill_has_the_plain_english_rules(self):
        skill = read("SKILL.md")
        self.assertTrue("## Plain English" in skill, "SKILL.md has no Plain English section")
        section = skill.split("## Plain English", 1)[1].split("\n## ", 1)[0]
        for term in ("ASD-STE100", "/wait-what", "25 words", "20 words", "door", "stop-line", "Don't know",
                     "Nothing found", "by-hand test", "scanner"):
            self.assertIn(term, section, term)


class DoorDoesNotMoveTests(unittest.TestCase):
    """Plain English rewrites words, never the rule: these files match the release byte for byte.

    This guards the wording-only release 0.3.6 against the release it left. A later release that changes the rule on
    purpose (0.4.0: answers read from the code) is held to the never-worse tests instead: custody_verdict_test's
    ReleasedVerdictNeverWorseTests and VerdictMatchesProseRuleTests, and custody_scan_test's NeverWorseThanMainTests."""

    @classmethod
    def setUpClass(cls):
        import custody_verdict as cv
        if cv.__version__ != "0.3.6":
            raise unittest.SkipTest("guards the wording-only release 0.3.6; later rule changes meet the never-worse tests")
        cls.ref = cst._release_ref(REPO_ROOT)
        if cls.ref is None:
            if cst.REQUIRE_GIT:
                raise AssertionError("no release ref to compare against")
            raise unittest.SkipTest("not a git checkout with main")

    def released(self, rel_path):
        out = subprocess.run(["git", "-C", REPO_ROOT, "show", "%s:%s" % (self.ref, rel_path)], capture_output=True)
        self.assertEqual(out.returncode, 0, rel_path)
        return out.stdout.decode("utf-8")

    def current(self, rel_path):
        with open(os.path.join(REPO_ROOT, rel_path), encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def outside_the_rewrite(text):
        """SKILL.md minus the two parts this PR rewrites: the new `## Plain English` section and the preflight message
        (its one `> ` line, found by its opening words). Everything else, every section that decides and any other
        `> ` line, must match the release byte for byte."""
        if "## Plain English\n" in text:
            head, rest = text.split("## Plain English\n", 1)
            text = head + "## " + rest.split("\n## ", 1)[1]
        preflight = [l for l in text.splitlines() if l.startswith("> This skill runs from the folder that contains your app")]
        assert len(preflight) == 1, "expected exactly one preflight message line, found %d" % len(preflight)
        return text.replace(preflight[0], "> PREFLIGHT", 1)

    @staticmethod
    def no_version(text):
        return re.sub(r'^__version__ = "[^"]+"$', "", text, flags=re.M)

    def test_skill_md_outside_the_rewrite_is_byte_identical(self):
        p = "custody-check/skills/custody-check/SKILL.md"
        self.assertEqual(self.outside_the_rewrite(self.current(p)), self.outside_the_rewrite(self.released(p)))
        doors = "custody-check/skills/custody-check/references/tiers-and-doors.md"
        self.assertEqual(self.current(doors), self.released(doors))

    def test_scanners_and_verdict_script_are_unchanged(self):
        base = "custody-check/skills/custody-check/scripts/"
        self.assertEqual(self.current(base + "custody_scan_0_3_2.py"), self.released(base + "custody_scan_0_3_2.py"))
        for name in ("custody_scan.py", "custody_verdict.py"):
            self.assertEqual(self.no_version(self.current(base + name)), self.no_version(self.released(base + name)), name)


if __name__ == "__main__":
    unittest.main()
