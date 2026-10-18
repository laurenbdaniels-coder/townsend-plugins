"""Plain English for what the founder reads (0.3.6, ASD-STE100 Simplified Technical English), and the free-plugin
report standard (0.5.0: count line first, diagnose only, never a fix).

What a founder reads: the verdict template's markdown block, the footer and partial-reason lines, the fixed lines
SKILL.md tells the agent to say, and the by-hand tests and checks in references/questions.md. No sentence there runs
over 25 words, and no instruction (a by-hand step, a check) over 20. The verdict opens with one line of context.

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
    r'Say: "([^"]+)"',                                      # the app folder is a shortcut (0.4.0)
    r'say once: "([^"]+)"',                                 # read it anyway: what the provider sees
    r'say instead: "([^"]+)"',                              # a refused folder: nothing read
    r'say exactly: "([^"]+)"',                              # a fix request (0.5.0)
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
    """Each `**By hand …:**` and `**Check it:**` bullet (with its numbered sub-steps) in questions.md."""
    out = []
    for m in re.finditer(r"^- \*\*(By hand[^*]*|Check it):\*\*(.*?)(?=^- |^#+ |\Z)", read("references", "questions.md"),
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

    def test_by_hand_steps_and_checks_are_at_most_20_words_a_sentence(self):
        blocks = by_hand_blocks()
        self.assertGreaterEqual(len(blocks), 17, "Q1-Q11 and A1-A6 each have a by-hand test")
        for head, body in blocks:
            for s in sentences(body):
                self.assertLessEqual(words(s), 20, "%s: %s" % (head, s))

    def test_title_then_count_then_why_then_context(self):
        """The free-plugin standard: nothing before the title, then the count line, then the fixed why line."""
        lines = [l for l in template_block().split("## Stop-line", 1)[0].splitlines() if l.strip()]
        self.assertTrue(lines[0].startswith("# Custody check: "), lines[0])
        self.assertRegex(lines[1], r"^<when .*> \*\*Your app has <N> <answer that is \| answers that are> No or Don't know\.\*\*$")
        self.assertRegex(lines[2], r"^<when .*> This run found no answer that is No or Don't know\.$")
        self.assertTrue(lines[3].startswith("Why this matters: "), lines[3])
        self.assertRegex(lines[4], r"(?i)^this check reads your app's files")
        self.assertRegex(lines[4], r"(?i)\bdoor\b")

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
        for term in ("ASD-STE100", "25 words", "20 words", "door", "stop-line", "Don't know",
                     "Nothing found", "by-hand test", "scanner"):
            self.assertIn(term, section, term)


def pack_pattern(name):
    """A shared grader's pattern from free-plugin-standard/pack.json, so these tests and the evals agree."""
    import json
    with open(os.path.join(REPO_ROOT, "free-plugin-standard", "pack.json"), encoding="utf-8") as fh:
        pack = json.load(fh)
    for group in pack["groups"].values():
        for g in group:
            if g["name"] == name:
                return re.compile(g["pattern"], re.I if "i" in g["flags"] else 0)
    raise AssertionError("no grader " + name)


WHY = ("Why this matters: a stranger can reach what your app does not protect. That can be a key, someone else's "
       "record, or an admin button. Nothing on screen shows it until someone tries.")
NOT_CHECKED = ("Not checked: the running app, your host's and your database's dashboards, settings that live outside "
               "your files, and code this run did not read. Not found does not mean it isn't there.")
POINTER = ("For a rule your app decides in more than one place (who can see a record, prices, paid status), "
           "run build-decisions.")


class FreePluginStandardTests(unittest.TestCase):
    """0.5.0: custody-check reports to free-plugin-standard/STANDARD.md, inside its own verdict shape."""

    def test_fixed_lines_appear_once_in_the_template(self):
        block = template_block()
        for line in (WHY, NOT_CHECKED, POINTER):
            self.assertEqual(block.count(line), 1, line)

    def test_order_after_the_eleven(self):
        block = template_block()
        at = [block.index(x) for x in ("## The eleven", "One place decides who is allowed:", "## Don't know",
                                       "**Before you change any of these:**", NOT_CHECKED, POINTER, "\n---\n")]
        self.assertEqual(at, sorted(at))
        self.assertTrue(block.rstrip().endswith("read-only · a review, not an audit"), block.rstrip()[-80:])

    def test_patch_items_use_the_standard_lines(self):
        patch = template_block().split("## Patch list", 1)[1].split("\n## ", 1)[0]
        self.assertIn("What could go wrong:", patch)
        self.assertIn("Check it (1 min):", patch)
        self.assertNotIn("If they get out of sync:", patch)

    def test_no_fix_steps_anywhere_the_founder_reads(self):
        fix = pack_pattern("std-no-fix-prompt")
        for name, text in (("template", read("assets", "verdict-template.md")),
                           ("questions", read("references", "questions.md")),
                           ("tiers", read("references", "tiers-and-doors.md")),
                           ("skill", read("SKILL.md"))):
            for bad in ("The fix:", "move it server-side", "set one.", "fix line", "has a fix beside it",
                        "ends with a fix"):
                self.assertNotIn(bad, text, "%s: %s" % (name, bad))
            if name != "skill":  # SKILL.md quotes the banned words to forbid them
                self.assertIsNone(fix.search(text), "%s: %s" % (name, fix.search(text) and fix.search(text).group(0)))

    def test_rotation_stays_as_a_safety_step(self):
        self.assertIn("rotate it now", read("assets", "verdict-template.md"))
        self.assertIn("Rotate that key now.", read("references", "questions.md"))

    def test_no_code_words_in_what_the_founder_reads(self):
        code = pack_pattern("std-no-code-words")
        texts = [re.sub(r"<[^>\n]*>", "", l) for l in template_block().splitlines()
                 if not l.startswith("(") and l.strip()]
        texts += [body for _, body in by_hand_blocks()]
        texts += quoted_lines(read("assets", "verdict-template.md")) + skill_founder_lines()
        # the tier line names the escalation trigger that fired, so the trigger list is founder text too
        texts += [read("references", "tiers-and-doors.md").split("**Escalation triggers", 1)[1].split("\n", 1)[0]]
        for t in texts:
            for line in t.splitlines():
                self.assertIsNone(code.search(line), line)

    def test_every_check_for_the_ai_tool_says_change_nothing(self):
        q = read("references", "questions.md")
        for m in re.finditer(r'Ask your AI tool: "([^"]+)"', q + read("assets", "verdict-template.md")):
            self.assertTrue(m.group(1).endswith("Change nothing."), m.group(1))

    def test_skill_has_the_free_paid_rule(self):
        skill = read("SKILL.md")
        self.assertIn("It does not fix, here or in another conversation.", skill)
        said = re.search(r'say exactly: "([^"]+)"', skill).group(1)
        self.assertIsNone(pack_pattern("std-no-fix-prompt").search(said), said)
        self.assertIsNone(pack_pattern("std-no-code-words").search(said), said)
        self.assertIn("never say what the text says or asks for", skill)
        self.assertIn("**Diagnose, never prescribe.**", skill)
        self.assertIn("Change nothing.", skill)
        self.assertNotIn("a founder handed a finding and no fix stops reading", skill)

    def test_wait_what_credit_is_gone(self):
        """S-038, as decision-census 0.3.2: ASD-STE100 stays, the /wait-what credit goes (CHANGELOG history stays)."""
        readme = open(os.path.join(SKILL_DIR, "..", "..", "README.md"), encoding="utf-8").read()
        for name, text in (("SKILL.md", read("SKILL.md")), ("README.md", readme)):
            self.assertNotIn("wait-what", text, name)
        self.assertIn("ASD-STE100", read("SKILL.md"))


class OnePlaceDecidesTests(unittest.TestCase):
    """S-007: the Q4 "one place decides?" line asks, points to build-decisions, and never reaches the door."""

    def test_questions_md_q4_has_the_line(self):
        q4 = read("references", "questions.md").split("## Q4.", 1)[1].split("## Q5.", 1)[0]
        self.assertIn("**One place decides?**", q4)
        self.assertIn("build-decisions", q4)
        self.assertRegex(q4, r"(?i)never changes the answer or the door")

    def test_skill_asks_it_and_keeps_it_out_of_the_scripts(self):
        skill = read("SKILL.md")
        self.assertIn("q4_one_place", skill)
        self.assertRegex(skill, r"`q4_one_place`[^.\n]*never goes in `<answers>` or `<read>`")

    def test_answers_example_has_the_field(self):
        self.assertRegex(read("assets", "founder-answers-example.md"), r"(?m)^q4_one_place: ")

    def test_template_renders_it_with_the_pointer(self):
        block = template_block()
        self.assertIn("One place decides who is allowed: <yes | no | don't know> (you).", block)
        self.assertIn("Run build-decisions to see each place your app decides it.", block)


class DoorDoesNotMoveTests(unittest.TestCase):
    """A wording-only release rewrites words, never the rule: what decides matches the release it left byte for byte.

    WORDING_ONLY lists those releases: 0.3.6 (plain English) and 0.5.0 (the free-plugin standard, the Q4 line, the
    credit). A release that changes the rule on purpose (0.4.0: answers read from the code) is held to the never-worse
    tests instead: custody_verdict_test's ReleasedVerdictNeverWorseTests and VerdictMatchesProseRuleTests, and
    custody_scan_test's NeverWorseThanMainTests."""

    WORDING_ONLY = {"0.3.6", "0.5.0"}

    @classmethod
    def setUpClass(cls):
        import custody_verdict as cv
        cls.version = cv.__version__
        if cls.version not in cls.WORDING_ONLY:
            raise unittest.SkipTest("guards wording-only releases; rule changes meet the never-worse tests")
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
    def section(text, heading, level="## "):
        """One markdown section, heading included, up to the next heading of the same level or higher."""
        body = text.split(heading + "\n", 1)[1]
        stops = ["\n## "] if level == "## " else ["\n## ", "\n### "]
        end = min([body.find(x) for x in stops if x in body] or [len(body)])
        return heading + "\n" + body[:end]

    @staticmethod
    def no_version(text):
        return re.sub(r'^__version__ = "[^"]+"$', "", text, flags=re.M)

    def test_door_rule_is_byte_identical(self):
        p = "custody-check/skills/custody-check/SKILL.md"
        self.assertEqual(self.section(self.current(p), "## Door rule"), self.section(self.released(p), "## Door rule"))
        doors = "custody-check/skills/custody-check/references/tiers-and-doors.md"
        for heading in ("### Door rule (applied in this order)", "### Patch-list order"):
            self.assertEqual(self.section(self.current(doors), heading, "### "),
                             self.section(self.released(doors), heading, "### "), heading)

    def test_scanners_and_verdict_script_are_unchanged(self):
        base = "custody-check/skills/custody-check/scripts/"
        self.assertEqual(self.current(base + "custody_scan_0_3_2.py"), self.released(base + "custody_scan_0_3_2.py"))
        for name in ("custody_scan.py", "custody_verdict.py"):
            self.assertEqual(self.no_version(self.current(base + name)), self.no_version(self.released(base + name)), name)

    def test_the_section_reader_catches_a_change(self):
        """Mutation guard: a one-word edit inside the door rule must show up as a difference."""
        text = self.released("custody-check/skills/custody-check/SKILL.md")
        mutated = text.replace("Two or more of Q4, Q5, Q6, Q9", "Three or more of Q4, Q5, Q6, Q9", 1)
        self.assertNotEqual(mutated, text)
        self.assertNotEqual(self.section(mutated, "## Door rule"), self.section(text, "## Door rule"))


if __name__ == "__main__":
    unittest.main()
