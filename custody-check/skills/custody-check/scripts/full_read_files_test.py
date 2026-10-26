"""Pins for the full read (custody-check 0.7.0, S-068).

The freeze: the text the main agent reads before its own Q1-Q4 read stays exactly 0.6.2's, because the
S-068 sample showed any change there moves its answers (a dropped stop-line on one app). SKILL.md may differ
from 0.6.2 only by the one pointer line; questions.md and the report template not at all. To change them on
purpose, rerun the never-worse differential and the sample's 4-app check first, then update the hash here.
"""
import hashlib
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
PLUGIN = os.path.dirname(os.path.dirname(SKILL_DIR))
POINTER = "After your own read above and before the founder's questions, follow `references/full-read.md`.\n"

SKILL_062 = "ef6b3938ea95f960d8d438e67d25f4c6cfe7c2097f1d62b9266768b6bba9fef8"
QUESTIONS_062 = "01271f2fd3466a511f66a7a23ec88a6c1534ed673b199455fbf073e506cc2251"
TEMPLATE_062 = "31c2f0efde5e6ee7023c49840be9244d93665730deef3b8fb89cff972040cb82"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def phrase_pairs():
    rows = re.findall(r"^\| (q\d+|a\d) \| ([a-z-]+) \| ", read(SKILL_DIR, "references", "evidence-phrases.md"), re.M)
    return {(q, t) for q, t in rows}


class FreezeTests(unittest.TestCase):
    def test_skill_is_062_plus_pointer(self):
        s = read(SKILL_DIR, "SKILL.md")
        self.assertEqual(s.count(POINTER), 1)
        self.assertEqual(sha(s.replace("\n" + POINTER, "", 1)), SKILL_062,
                         "SKILL.md changed beyond the full-read pointer line; see this file's docstring")

    def test_pointer_sits_before_answer_rules(self):
        s = read(SKILL_DIR, "SKILL.md")
        self.assertLess(s.index(POINTER), s.index("## Answer rules"))
        self.assertGreater(s.index(POINTER), s.index("## Read the code"))

    def test_questions_and_template_unchanged(self):
        self.assertEqual(sha(read(SKILL_DIR, "references", "questions.md")), QUESTIONS_062)
        self.assertEqual(sha(read(SKILL_DIR, "assets", "verdict-template.md")), TEMPLATE_062)


class HelperAgentTests(unittest.TestCase):
    def setUp(self):
        self.text = read(PLUGIN, "agents", "full-read-helper.md")
        m = re.match(r"---\n(.*?)\n---\n", self.text, re.S)
        self.assertIsNotNone(m, "frontmatter")
        self.front = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)

    def test_frontmatter(self):
        self.assertEqual(self.front["name"].strip(), "full-read-helper")
        self.assertEqual(self.front["tools"].strip(), "Read")
        self.assertTrue(self.front["description"].strip())

    def test_types_match_phrase_list(self):
        listed = set(re.findall(r"^- `(q\d+|a\d)` `([a-z-]+)`:", self.text, re.M))
        self.assertEqual(listed, phrase_pairs())

    def test_helper_writes_no_sentences(self):
        self.assertNotIn('"what"', self.text)
        self.assertIn("You write no sentences", self.text)


class PhraseTests(unittest.TestCase):
    def test_every_question_has_an_ending(self):
        text = read(SKILL_DIR, "references", "evidence-phrases.md")
        endings = set(re.findall(r"^\| (q\d+|a\d) \| this does not show", text, re.M))
        self.assertEqual(endings, {q for q, _ in phrase_pairs()})

    def test_no_phrase_claims_absence_or_safety(self):
        text = read(SKILL_DIR, "references", "evidence-phrases.md").lower()
        for bad in ("no backup", "is safe", "is secure", "nothing", "never fails"):
            self.assertNotIn("| " + bad, text)

    def test_full_read_names_the_helper_and_phrases(self):
        text = read(SKILL_DIR, "references", "full-read.md")
        self.assertIn("custody-check:full-read-helper", text)
        self.assertIn("references/evidence-phrases.md", text)
        self.assertIn("full_read_slices.py", text)
        self.assertNotIn("S068-EVIDENCE", text)


def _no_code_words():
    import json
    with open(os.path.join(os.path.dirname(PLUGIN), "free-plugin-standard", "pack.json"), encoding="utf-8") as fh:
        pack = json.load(fh)
    found = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("name") == "std-no-code-words":
                found.append(o["pattern"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(pack)
    return re.compile(found[0], re.I)


class ReportWordsTests(unittest.TestCase):
    """Every fixed sentence the full read adds to a report passes the standard's no-code-words grader."""

    def test_phrases_and_endings(self):
        rx = _no_code_words()
        text = read(SKILL_DIR, "references", "evidence-phrases.md")
        cells = re.findall(r"^\| (?:q\d+|a\d) \| [a-z-]+ \| ([^|]+) \|", text, re.M)
        cells += re.findall(r"^\| (?:q\d+|a\d) \| (this does not show[^|]+) \|", text, re.M)
        self.assertGreater(len(cells), 40)
        for c in cells:
            self.assertIsNone(rx.search("\n" + c), c)

    def test_quoted_report_lines(self):
        rx = _no_code_words()
        text = read(SKILL_DIR, "references", "full-read.md")
        lines = re.findall(r'"([A-Z<][^"]{10,})"', text)
        self.assertGreater(len(lines), 4)
        for l in lines:
            self.assertIsNone(rx.search("\n" + l), l)


if __name__ == "__main__":
    unittest.main()
