"""Plain English for what the founder reads (0.3.6, ASD-STE100 Simplified Technical English), and the free-plugin
report standard (0.5.0: count line first, diagnose only, never a fix). 0.6.0: the plain report says what is broken and
what it means, never what to do (no door, no eleven, no Check it lines, no AI-tool questions, no link, no pointer).

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
    r'Ask it first, as "([^"]+)"',                          # the stop-line question
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

    def test_title_then_count_then_why_then_coverage(self):
        """The free-plugin standard: nothing before the title, then the count line, then the fixed why line. 0.6.0 adds
        the coverage line right after it (plan 1e)."""
        lines = [l for l in template_block().split("<only when the stop-line", 1)[0].splitlines() if l.strip()]
        self.assertTrue(lines[0].startswith("# Custody check: "), lines[0])
        self.assertTrue(lines[1].startswith("<count line"), lines[1])
        self.assertTrue(lines[2].startswith("Why this matters: "), lines[2])
        self.assertTrue(lines[3].startswith("<coverage line"), lines[3])
        self.assertEqual(len(lines), 4, lines)

    def test_count_line_forms(self):
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        for form in ("**We found <P> <problem | problems> in your code, and <Q> <thing | things> your code can't tell us.**",
                     "**We found <P> <problem | problems> in your code, and nothing else your code can't tell us.**",
                     "**We found no problems in your code, and <Q> <thing | things> your code can't tell us.**",
                     "**We found no problems in your code, and your code and your answers settled every question we ask.**"):
            self.assertIn(form, rules)

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
        for term in ("ASD-STE100", "25 words", "20 words", "stop-line", "Don't know", "Nothing found",
                     "by-hand test", "scanner", "What it means for you", "never what to do"):
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


def report_lines():
    """Each questions.md `**In the report:**` line: the problem title, its meaning and the open-question bullet."""
    return re.findall(r"^- \*\*In the report:\*\*(.*)$", read("references", "questions.md"), re.M)


WHY = ("Why this matters: a stranger can reach what your app does not protect. That can be a key, someone else's "
       "record, or an admin button. Nothing on screen shows it until someone tries.")
NOT_CHECKED = ("We also can't see your live site, your hosting and database dashboards, or settings stored outside your "
               "code. Not found does not mean it isn't there.")


class FreePluginStandardTests(unittest.TestCase):
    """0.5.0: custody-check reports to free-plugin-standard/STANDARD.md, inside its own verdict shape."""

    def test_fixed_lines_appear_once_in_the_template(self):
        block = template_block()
        for line in (WHY, NOT_CHECKED):
            self.assertEqual(block.count(line), 1, line)

    def test_report_order(self):
        block = template_block()
        at = [block.index(x) for x in ("# Custody check:", "Why this matters:", "<coverage line", "carries extra risk.**",
                                       "**Do today:**", "## What we found in your code", "## What your code can't tell us",
                                       NOT_CHECKED, "\n---\n")]
        self.assertEqual(at, sorted(at))
        self.assertTrue(block.rstrip().endswith("custody-check v<version from the scanner JSON> · read-only · a review, not an audit"),
                        block.rstrip()[-80:])

    def test_problem_blocks_use_the_standard_lines(self):
        found = template_block().split("## What we found in your code", 1)[1].split("\n## ", 1)[0]
        self.assertIn("What it means for you:", found)
        self.assertIn("Where: `<path>:<line>`, `<path>:<line>`", found)  # at most 2 places
        for gone in ("Check it", "What could go wrong:", "If they get out of sync:", "(Q<n>)"):
            self.assertNotIn(gone, found)

    def test_says_what_is_broken_never_what_to_do(self):
        """Owner answer 4 (plan 1f): no advice line, no Check it, no AI-tool questions, no Before you change line, no
        pointer, no link. Do today (a key was seen) and the rerun line are the two kept instructions."""
        block = template_block()
        for gone in ("Our advice", "Check it", "Ask your AI tool", "ask your AI tool", "Change nothing", "Before you change",
                     "build-decisions", "townsendaistudio", "assessment", "## The eleven", "## Door", "Get a person",
                     "Ship it", "Patch it", "## Stop-line", "## Next change", "## Patch list", "## Rotate now",
                     "Keeping the AI on rails", "Five, if you'll only do five", "One place decides who is allowed:"):
            self.assertNotIn(gone, block, gone)
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        never = rules.split("**Never in the report:**", 1)[1].split("\n- ", 1)[0]
        for word in ("door", "stop-line", "scanner", "eleven", "tier", "by-hand test", "Check it", "AI tool",
                     "studio link", "another plugin"):
            self.assertIn(word, never, word)

    def test_problems_never_count_dont_know(self):
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        self.assertIn('P is the number of problem blocks under "What we found in your code".', rules)
        self.assertIn('Q is the number of bullets under "What your code can\'t tell us".', rules)
        self.assertIn("one block per row answered No", rules)
        self.assertIn("one bullet per row in `verdict.dont_know` (Don't know and Nothing found", rules)
        self.assertIn("**Joining:** when every place of a row is already shown by an earlier block", rules)

    def test_extra_risk_block_is_a_fact_and_shows_without_problems(self):
        """The stop-line reason's home (step 3, Lauren's pick): its own block above Do today, not counted in P, so it
        still shows when P is 0. It states what carries the risk and what a mistake costs, never who to call."""
        block = template_block()
        risk = block.split("<only when the stop-line is ticked:>", 1)[1].split("<only when a key was seen:>", 1)[0]
        self.assertIn("What it means for you:", risk)
        self.assertIn("Where:", risk)
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        part = rules.split("**The extra-risk block**", 1)[1].split("\n- **", 1)[0]
        self.assertIn("not counted in P", part)
        self.assertIn("never say who to call", part)
        for advice in ("get a person", "expert", "professional", "write to", "before your next change"):
            self.assertNotIn(advice, part.lower(), advice)
        self.assertNotIn("P is 0", block.split("<only when the stop-line is ticked:>", 1)[0])

    def test_no_five(self):
        for name in (("assets", "verdict-template.md"), ("SKILL.md",), ("references", "tiers-and-doors.md")):
            self.assertNotIn("Five, if you'll only do five", read(*name), name)

    def test_nothing_after_the_footer(self):
        """Step 6 eval runs: the agent added notes after the footer that used the workshop words."""
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        self.assertIn("nothing after the footer", rules)
        self.assertIn("end the message with its footer: nothing after it", read("SKILL.md"))

    def test_review_round_1_rules(self):
        """Review round 1: the inventory marks are hints; a founder's No never joins away; the fallback line only on a
        scan that finished; rule 1's fix reply may follow the footer."""
        skill = read("SKILL.md")
        self.assertIn("The `s` and `h` marks are hints from paths and patterns, never proof.", skill)
        self.assertIn("Never answer Q2 or Q4 from the marks", skill)
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        self.assertIn("A row with no places (a No from the founder's answers) never joins", rules)
        self.assertIn("`stats.overlay_fallback` is not null and `partial` is false", rules)
        self.assertIn("when the founder asked for a fix, SKILL.md rule 1's sentence follows the footer", rules)
        self.assertIn("except rule 1's sentence when the founder asked for a fix", skill)

    def test_extra_risk_meaning_is_two_sentences_and_do_today_counts_no_rows(self):
        """Step 6 eval runs: an 80-word risk block pushed the first screen past 150 words, and Do today counted
        settings files on disk as keys."""
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        self.assertIn("What it means for you: exactly two sentences.", rules)
        self.assertIn("one sentence of at most 20 words", rules)
        self.assertIn("`env-file-on-disk` are never counted", rules)

    CAPPED_KEPT = "The scan found more such fields than this report can list."
    CAPPED_NONE = "Your app keeps personal-data fields the scan could not list here, and that carries extra risk."

    def risk_rules(self):
        rules = read("assets", "verdict-template.md").split("Rules for filling it in:", 1)[1]
        return rules.split("**The extra-risk block**", 1)[1].split("\n- **Do today**", 1)[0]

    def test_capped_states_are_written_down(self):
        """S-062: when the scan dropped stop-line fields to fit (verdict.stop_line.capped), the report says so in one
        fixed sentence. Fields kept: the title names only those, plus CAPPED_KEPT. None kept: CAPPED_NONE is the title
        (or the line under a title the founder's or your reading's items give), and there is no Where line."""
        part = self.risk_rules()
        self.assertIn("`verdict.stop_line.capped`", part)
        self.assertIn('"%s"' % self.CAPPED_KEPT, part)
        self.assertIn('"%s"' % self.CAPPED_NONE, part)
        self.assertIn("no Where line", part)
        self.assertIn("never ordinary fields", part)
        for sentence in (self.CAPPED_KEPT, self.CAPPED_NONE):
            self.assertLessEqual(words(sentence), 25)
            self.assertNotIn("read", sentence)  # an evidence limit, not the "files not read" wording
        self.assertIn("<only when `verdict.stop_line.capped` is true:", template_block())

    def test_where_comes_from_the_verdict(self):
        part = self.risk_rules()
        self.assertIn("`verdict.stop_line.where`", part)
        skill = read("SKILL.md")
        self.assertIn("the extra-risk block from `verdict.stop_line` (`ticked`, `where`, `capped`, and the items in "
                      "`founder`, `fields` and `read`)", skill)

    def test_the_cap_count_never_reaches_the_report(self):
        """The stat is the script's; the founder sees only the fixed sentence (DD11)."""
        self.assertNotIn("capped", template_block().replace("`verdict.stop_line.capped`", ""))
        self.assertNotIn("stopline_rows_capped", template_block())
        self.assertIn("Never print the count or its name.", self.risk_rules())

    def test_short_footer(self):
        skill = read("SKILL.md").split("## Footer", 1)[1]
        self.assertIn("custody-check v<version from the JSON> · read-only · a review, not an audit", skill)
        self.assertNotIn("files scanned", skill)

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
        for said in skill_founder_lines():  # what SKILL.md tells the agent to say to the founder
            self.assertIsNone(fix.search(said), said)

    def test_q3_still_tests_the_request_not_only_the_page(self):
        """Main said "URL or API endpoint". A protected page can load an open record, so the request is tested too."""
        q3 = read("references", "questions.md").split("**Logged out:**", 1)[1].split("\n", 1)[0]
        # copy it while logged in, then open it logged out: a page that redirects to log in never loads it
        for word in ("logged in, copy the request", "network tab", "Open it in a private window"):
            self.assertIn(word, q3)
        # 0.6.0: the five left the template and tiers-and-doors.md, so the words live in Q3's by-hand test
        q3_all = read("references", "questions.md").split("## Q3.", 1)[1].split("## Q4.", 1)[0]
        self.assertIn("each request a screen sends", q3_all.split("**By hand", 1)[1].split("- **In the report", 1)[0])

    def test_rotation_stays_as_a_safety_step(self):
        self.assertIn("**Do today:** replace <n> secret <key | keys> with new ones. Treat the old ones as already stolen.",
                      template_block())
        self.assertIn("Rotate that key now.", read("references", "questions.md"))

    def test_no_code_words_in_what_the_founder_reads(self):
        code = pack_pattern("std-no-code-words")
        texts = [re.sub(r"<[^>\n]*>", "", l) for l in template_block().splitlines()
                 if not l.startswith("(") and l.strip()]
        texts += [body for _, body in by_hand_blocks()]
        texts += report_lines()
        texts += quoted_lines(read("assets", "verdict-template.md")) + skill_founder_lines()
        # the chat may name the escalation trigger that fired (tiers stay in the chat, never the report), so it is founder text too
        texts += [read("references", "tiers-and-doors.md").split("**Escalation triggers", 1)[1].split("\n", 1)[0]]
        for t in texts:
            for line in t.splitlines():
                self.assertIsNone(code.search(line), line)

    def test_every_check_for_the_ai_tool_says_change_nothing(self):
        q = read("references", "questions.md")
        asks = re.findall(r'Ask your AI tool(?: to)?:? "([^"]+)"', q + read("assets", "verdict-template.md"), re.I)
        self.assertGreaterEqual(len(asks), 6, asks)  # A1, A2 (two), A3, A5, A6: chat only since 0.6.0
        for said in asks:
            self.assertTrue(said.endswith("Change nothing."), said)

    def test_skill_has_the_no_fix_rule(self):
        skill = read("SKILL.md")
        self.assertIn("It does not fix, here or in another conversation, and it does not suggest fixes.", skill)
        said = re.search(r'say exactly: "([^"]+)"', skill).group(1)
        self.assertIsNone(pack_pattern("std-no-fix-prompt").search(said), said)
        self.assertIsNone(pack_pattern("std-no-code-words").search(said), said)
        self.assertIn("never say what the text says or asks for", skill)
        self.assertIn("**Find, never fix.**", skill)
        self.assertIn("Change nothing.", skill)
        self.assertNotIn("a founder handed a finding and no fix stops reading", skill)

    def test_wait_what_credit_is_gone(self):
        """S-038, as decision-census 0.3.2: ASD-STE100 stays, the /wait-what credit goes (CHANGELOG history stays)."""
        readme = open(os.path.join(SKILL_DIR, "..", "..", "README.md"), encoding="utf-8").read()
        for name, text in (("SKILL.md", read("SKILL.md")), ("README.md", readme)):
            self.assertNotIn("wait-what", text, name)
        self.assertIn("ASD-STE100", read("SKILL.md"))


class ReportLinesTests(unittest.TestCase):
    """0.6.0: questions.md gives each question its plain report wording, so the agent does not invent it."""

    def test_every_question_has_a_report_line(self):
        q = read("references", "questions.md")
        for head in ["Q%d" % n for n in range(1, 12)] + ["A%d" % n for n in range(1, 7)]:
            section = re.split(r"\n#{1,2} ", q.split("## %s. " % head, 1)[1], maxsplit=1)[0]
            self.assertEqual(section.count("- **In the report:** a No is the problem \""), 1, head)

    def test_report_lines_are_plain_and_never_say_what_to_do(self):
        fix = pack_pattern("std-no-fix-prompt")
        lines = report_lines()
        self.assertEqual(len(lines), 17)
        for line in lines:
            self.assertIsNone(fix.search(line), line)
            for said in re.findall(r'"([^"]+)"', line):
                for s in sentences(said):
                    self.assertLessEqual(words(s), 25, s)
            for bad in ("ask your AI tool", "Ask your AI tool", "Change nothing", "Check", "rotate", "run build-decisions", "Q1", "door"):
                self.assertNotIn(bad, line, bad)


class QuestionRuleTests(unittest.TestCase):
    """free-plugin-standard/SCOPE.md (Lauren, 2026-10-21): never ask what the code should show; ask the stop-line only
    when the code does not show it; each question may carry its one-minute test, in the chat only."""

    def interview(self):
        return read("SKILL.md").split("## Founder answers", 1)[1].split("\n## ", 1)[0]

    def test_scope_is_written_down_and_named_by_the_skill(self):
        with open(os.path.join(REPO_ROOT, "free-plugin-standard", "SCOPE.md"), encoding="utf-8") as fh:
            scope = fh.read()
        self.assertIn("Never ask what the code should show.", scope)
        self.assertIn("free-plugin-standard/SCOPE.md", self.interview())

    def test_never_asks_what_the_code_should_show(self):
        text = self.interview()
        self.assertIn("**Never ask** Q1 (keys), Q2 (browser or server), Q3 (who can read), Q4 (who can change)", text)
        then = text.split("**Then ask**", 1)[1].split("\n", 1)[0]
        for q in (r"\bQ1\b", r"\bQ2\b", r"\bQ3\b", r"\bQ4\b", r"one place"):
            self.assertNotRegex(then, q)
        self.assertNotIn("Is there one place in your app that decides who is allowed to do this?", read("SKILL.md"))

    def test_stop_line_is_asked_only_when_the_code_does_not_show_it(self):
        self.assertIn("**Ask the stop-line only when the code does not already show it**", self.interview())

    def test_tests_go_with_questions_in_the_chat_only(self):
        self.assertIn("Offer the by-hand test from `references/questions.md` with each question, in the chat only; it "
                      "never goes in the report.", self.interview())

    def test_one_place_is_gone_from_the_report_and_the_example(self):
        rules = read("assets", "verdict-template.md")
        self.assertNotIn("one-place", rules)
        self.assertNotIn("q4_one_place", read("assets", "founder-answers-example.md"))
        q4 = read("references", "questions.md").split("## Q4.", 1)[1].split("## Q5.", 1)[0]
        self.assertIn("No longer asked (2026-10-21", q4)
        self.assertRegex(read("SKILL.md"), r"`q4_one_place` is no longer asked or used[^\n]*never goes in `<answers>` or `<read>`")


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
        # what the agent answers from and when the stop-line ticks: wording-only releases leave these too
        self.assertEqual(self.section(self.current(p), "## Answer rules"), self.section(self.released(p), "## Answer rules"))
        self.assertEqual(self.section(self.current(doors), "## The stop-line"),
                         self.section(self.released(doors), "## The stop-line"))

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
