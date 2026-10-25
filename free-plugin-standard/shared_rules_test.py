"""shared/shared_rules.py: the stop-line field list and matcher both free plugins use (S-062).

custody-check and build-decisions each ship a byte-identical copy of shared/shared_rules.py
(sync_shared.py keeps them equal). These tests pin the canonical file.

Run: python3 -m unittest discover -s free-plugin-standard -p '*_test.py' -v
"""
import ast
import glob
import importlib.util
import os
import random
import sys
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "shared"))

import shared_rules as sr  # noqa: E402

CUSTODY_SCRIPTS = os.path.join(ROOT, "custody-check", "skills", "custody-check", "scripts")
BD_SCRIPTS = os.path.join(ROOT, "build-decisions", "skills", "build-decisions", "scripts")


def terms(text, kind, **kw):
    return [(n, t) for n, _ident, t in sr.stopline_line_terms(text, kind, **kw)]


class FieldListTests(unittest.TestCase):
    def test_list_is_custodys_twelve_then_birth_date_and_birthday(self):
        self.assertEqual(sr.STOPLINE_FIELDS, (
            "ssn", "social_security", "dob", "date_of_birth", "birthdate", "medical", "diagnosis",
            "credit_card", "card_number", "cc_number", "iban", "passport", "birth_date", "birthday"))


class StoplineTermsTests(unittest.TestCase):
    def test_hits(self):
        for ident, want in (("birthday", ["birthday"]), ("userBirthday", ["birthday"]),
                            ("birth_date", ["birth_date"]), ("dateOfBirth", ["date_of_birth"]),
                            ("creditcard", ["credit_card"]), ("credit_card", ["credit_card"]),
                            ("ssn_last4", ["ssn"]), ("birthDate", ["birth_date"]), ("DOB", ["dob"])):
            with self.subTest(ident=ident):
                self.assertEqual(sr.stopline_terms(ident), want)

    def test_misses(self):
        for ident in ("dobby", "assessment", "email", "", "_", "card", "birth"):
            with self.subTest(ident=ident):
                self.assertEqual(sr.stopline_terms(ident), [])

    def test_pinned_cases(self):
        self.assertEqual(sr.stopline_terms("birth_date"), ["birth_date"])
        self.assertEqual(sr.stopline_terms("creditcard"), ["credit_card"])
        self.assertEqual(sr.stopline_terms("creditcardnumber"), ["credit_card"])  # tie with card_number: list order
        self.assertEqual(sr.stopline_terms("medical_diagnosis"), ["medical", "diagnosis"])
        self.assertEqual(sr.stopline_terms("medical_creditcard"), ["medical"])  # run-together only when (a) is empty

    def test_run_together_keeps_the_single_longest(self):
        # socialsecuritynumber holds social_security (14 letters); no other 6+ letter term
        self.assertEqual(sr.stopline_terms("socialsecuritynumber"), ["social_security"])
        # dateofbirth (11) beats birthdate? no: "dateofbirthdate" holds both; the longer wins
        self.assertEqual(sr.stopline_terms("dateofbirthdate"), ["date_of_birth"])

    def test_short_terms_never_match_run_together(self):
        for ident in ("ssnumber", "dobson", "ibanez", "xssn"):
            with self.subTest(ident=ident):
                self.assertEqual(sr.stopline_terms(ident), [])

    def test_known_false_positives_are_pinned_as_such(self):
        # Reports only get more cautious; these are the measured price (plan section 9 caps them).
        self.assertEqual(sr.stopline_terms("birthday_party"), ["birthday"])  # whole word
        self.assertEqual(sr.stopline_terms("passportscount"), ["passport"])  # run-together
        self.assertEqual(sr.stopline_terms("paramedical_staff"), ["medical"])
        self.assertEqual(sr.stopline_terms("biomedicalDevice"), ["medical"])

    def test_one_word_match_never_starts_inside_an_earlier_word(self):
        """Review round 1: accNumber read as cc_number. A run-together term that reaches into the next word must start
        at a word's start; inside one word it may start anywhere (custody's released verdict did that)."""
        self.assertEqual(sr.stopline_terms("accNumber"), [])
        self.assertEqual(sr.stopline_terms("acc_number"), [])
        self.assertEqual(sr.stopline_terms("creditcardNumber"), ["credit_card"])
        self.assertEqual(sr.stopline_terms("userbirthdate"), ["birthdate"])
        self.assertEqual(sr.stopline_terms("user_creditcard"), ["credit_card"])

    def test_results_are_copies(self):
        out = sr.stopline_terms("dateOfBirth")
        out.append("x")
        self.assertEqual(sr.stopline_terms("dateOfBirth"), ["date_of_birth"])

    def test_returns_a_list_of_list_members_only(self):
        out = sr.stopline_terms("user_ssn_creditcard")
        self.assertIsInstance(out, list)
        self.assertEqual(out, ["ssn"])

    def test_fuzz_only_list_members_come_back(self):
        rng = random.Random(62)
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_éßøДж中😀 -."
        fields = set(sr.STOPLINE_FIELDS)
        for _ in range(3000):
            ident = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 60)))
            if rng.random() < 0.3:
                ident += rng.choice(sr.STOPLINE_FIELDS).replace("_", rng.choice(["", "_", ""]))
            out = sr.stopline_terms(ident)
            self.assertTrue(set(out) <= fields, (ident, out))
            self.assertEqual(len(out), len(set(out)))

    def test_very_long_identifier_is_fast(self):
        ident = "x" * 200000 + "creditcard" + "y" * 200000
        t0 = time.monotonic()
        self.assertEqual(sr.stopline_terms(ident), ["credit_card"])
        self.assertLess(time.monotonic() - t0, 1.0)


class WholeTermsTests(unittest.TestCase):
    def test_whole_terms_are_step_a_only(self):
        self.assertEqual(sr.stopline_whole_terms("user_birthday"), ["birthday"])
        self.assertEqual(sr.stopline_whole_terms("creditcard"), [])
        self.assertEqual(sr.stopline_whole_terms("medical_diagnosis"), ["medical", "diagnosis"])

    def test_terms_equal_whole_terms_when_there_are_any(self):
        for ident in ("birthday", "creditcard", "dateOfBirth", "medical_creditcard", "passportscount", "x"):
            whole = sr.stopline_whole_terms(ident)
            if whole:
                self.assertEqual(sr.stopline_terms(ident), whole)


class KindTests(unittest.TestCase):
    def test_kind_by_file_name(self):
        for name, kind in (("001_init.sql", "sql"), ("x.PSQL", "sql"), ("a.pgsql", "sql"), ("a.ddl", "sql"),
                           ("schema.prisma", "slash"), ("types.ts", "slash"), ("model.js", "slash"),
                           ("models.py", "hash"), ("schema.rb", "hash"),
                           ("schema.graphql", "graphql"), ("s.gql", "graphql")):
            with self.subTest(name=name):
                self.assertEqual(sr.stopline_kind(name), kind)


class LineTermsTests(unittest.TestCase):
    def test_yields_lazily_with_line_identifier_and_term(self):
        gen = sr.stopline_line_terms("id int,\n  dateOfBirth date,\n", "sql")
        self.assertIsInstance(gen, types.GeneratorType)
        self.assertEqual(list(gen), [(2, "dateOfBirth", "date_of_birth")])

    def test_unknown_kind_is_an_error(self):
        with self.assertRaises(ValueError):
            list(sr.stopline_line_terms("x", "html"))

    def test_sql_comments_and_values_never_hit(self):
        text = ("-- birthday\n"
                "/* creditcard payments */\n"
                "/*\n stores medical notes\n*/\n"
                "create table t (passport text);\n"
                "insert into t values ('creditcard');\n")
        self.assertEqual(terms(text, "sql"), [(6, "passport")])

    def test_sql_quoted_identifiers_hit(self):
        text = 'CREATE TABLE "User" (\n  "dateOfBirth" TIMESTAMP(3),\n  `credit_card` TEXT\n);\n'
        self.assertEqual(terms(text, "sql"), [(2, "date_of_birth"), (3, "credit_card")])

    def test_sql_doubled_quote_stays_one_string(self):
        self.assertEqual(terms("values ('it''s my birthday'), ssn\n", "sql"), [(1, "ssn")])

    def test_sql_string_across_lines_is_dropped_and_lines_hold(self):
        self.assertEqual(terms("x = 'a\nbirthday\nb', \ndob int\n", "sql"), [(4, "dob")])

    def test_unterminated_quote_never_hides_the_rest_of_the_file(self):
        self.assertEqual(terms("note text default 'oops,\nbirthday date\n", "sql"), [(2, "birthday")])
        self.assertEqual(terms("x = \"oops\nbirthday DateTime\n", "slash"), [(2, "birthday")])

    def test_dollar_quoted_function_bodies_stay_code(self):
        text = "create function f() returns trigger as $$\nbegin new.birthday := now(); end;\n$$ language plpgsql;\n"
        self.assertEqual(terms(text, "sql"), [(2, "birthday")])

    def test_prisma_comments_never_hit_and_the_next_field_does(self):
        text = ("// birthday\n"
                "/// date of birth\n"
                "model User {\n"
                "  /*\n   stores medical notes\n  */\n"
                "  creditcard String\n"
                "  note String @default(\"passport card\")\n"
                "}\n")
        self.assertEqual(terms(text, "slash"), [(7, "credit_card")])

    def test_prisma_map_arguments_are_identifiers(self):
        text = 'model User {\n  dob DateTime @map("date_of_birth")\n  @@map("medical_records")\n}\n'
        self.assertEqual(terms(text, "slash"), [(2, "dob"), (2, "date_of_birth"), (3, "medical")])

    def test_slash_drops_prose_in_both_quote_styles_and_keeps_backticks(self):
        self.assertEqual(terms("a = 'an ssn'; b = \"iban here\"; c = `passport`\n", "slash"), [(1, "passport")])

    def test_slash_string_with_escaped_quote(self):
        self.assertEqual(terms('a = "x\\"birthday"; dob\n', "slash"), [(1, "dob")])

    def test_slash_url_in_a_string_does_not_start_a_comment(self):
        self.assertEqual(terms('url = "https://x"; birthday\n', "slash"), [(1, "birthday")])

    def test_slash_line_starting_with_star_or_html_comment_is_a_comment(self):
        self.assertEqual(terms("  * birthday\n  <!-- ssn -->\niban\n", "slash"), [(3, "iban")])

    def test_slash_hash_is_not_a_comment(self):
        self.assertEqual(terms("class U {\n  #birthday: Date\n}\n", "slash"), [(2, "birthday")])

    def test_hash_comments_and_strings(self):
        text = ("class P(models.Model):\n"
                "    # passport number\n"
                "    note = models.TextField(default='no ssn here')\n"
                "    birthday = models.DateField()  # dob\n")
        self.assertEqual(terms(text, "hash"), [(4, "birthday")])

    def test_graphql_hash_comments_and_descriptions(self):
        text = ('# ssn\ntype User {\n  "the passport"\n  birthday: String # iban\n}\n')
        self.assertEqual(terms(text, "graphql"), [(4, "birthday")])

    def test_a_quoted_single_name_is_a_field_name(self):
        """Review round 1 (S-062): Rails schema.rb, knex, SQLAlchemy Column(), quoted object keys and Prisma @map write
        column names as strings; main build-decisions matched them, so dropping them lost its hints."""
        for kind, text, want in (
                ("hash", 'create_table "patients" do |t|\n  t.string "ssn"\n  t.date "date_of_birth"\nend\n',
                 [(2, "ssn"), (3, "date_of_birth")]),
                ("slash", "table.string('ssn');\n", [(1, "ssn")]),
                ("hash", 'tax_id = Column("ssn", String)\n', [(1, "ssn")]),
                ("slash", 'z.object({ "dob": z.string() })\n', [(1, "dob")])):
            with self.subTest(text=text):
                self.assertEqual(terms(text, kind), want)

    def test_a_quoted_word_counts_only_as_a_whole_word(self):
        """A quoted value such as 'creditcard' may be a value, not a name: only main's whole-word rule applies to it."""
        self.assertEqual(terms("method: 'creditcard',\nkind: \"paymentmethod\"\n", "slash"), [])

    def test_escaped_quotes_on_one_line_stay_linear(self):
        """Review round 1: each unclosed quote on a line rescanned the rest of the line."""
        for kind in ("slash", "hash", "graphql"):
            text = 'ssn = 1\nx = "' + '\\"' * 150000 + "\n"
            t0 = time.monotonic()
            self.assertEqual(terms(text, kind), [(1, "ssn")])
            self.assertLess(time.monotonic() - t0, 2.0, kind)

    def test_sql_value_never_runs_past_a_statement_end(self):
        """Review round 1: a MySQL dump's \\' put a quote out of step and blanked every later table."""
        text = ("INSERT INTO people VALUES ('O\\'Brien'),('x');\n"
                "CREATE TABLE patients (\n  ssn text,\n  note text DEFAULT 'a'\n);\n")
        self.assertEqual(terms(text, "sql"), [(3, "ssn")])

    def test_sql_hash_line_is_a_mysql_comment(self):
        text = "# don't edit\nCREATE TABLE p (\n  ssn text,\n  note text DEFAULT 'x'\n);\n"
        self.assertEqual(terms(text, "sql"), [(3, "ssn")])

    def test_insert_heavy_sql_stays_fast(self):
        """Review round 1: seed files name a term on every row; each name's terms are worked out once."""
        text = "insert into t5 (id, name, dob) values (1, 'a', '2000-01-01');\n" * 40000
        t0 = time.monotonic()
        self.assertEqual(sum(1 for _ in sr.stopline_line_terms(text, "sql")), 40000)
        self.assertLess(time.monotonic() - t0, 1.5)

    def test_crlf_keeps_line_numbers(self):
        self.assertEqual(terms("a\r\n-- dob\r\nbirthday\r\n", "sql"), [(3, "birthday")])

    def test_two_terms_on_one_line_both_come_back(self):
        self.assertEqual(terms("email text, birthday date, ssn text\n", "sql"), [(1, "birthday"), (1, "ssn")])

    def test_clip_drops_text_past_the_limit(self):
        line = "a " * 30 + "birthday"
        self.assertEqual(terms(line, "sql", clip=20), [])
        self.assertEqual(terms(line, "sql", clip=200), [(1, "birthday")])

    def test_512_kb_sql_file_is_linear(self):
        chunk = "create table t (id int, email text, note text default 'x'); -- c\n/* b */\n"
        text = chunk * (512 * 1024 // len(chunk)) + "birthday date\n"
        t0 = time.monotonic()
        out = terms(text, "sql")
        self.assertLess(time.monotonic() - t0, 3.0)
        self.assertEqual(out, [(text.count("\n"), "birthday")])

    def test_one_huge_line_is_linear(self):
        text = ("'x' " * 150000) + "birthday"
        t0 = time.monotonic()
        self.assertEqual(terms(text, "slash"), [(1, "birthday")])
        self.assertLess(time.monotonic() - t0, 3.0)

    def test_a_file_with_no_term_letters_is_not_stripped(self):
        """custody's reading-cost ratchet: a file that holds no term's letters anywhere cannot hit, so it costs one
        search, not a strip (each hit's letters, underscores removed, sit in the whole file's)."""
        calls = []
        real = sr.strip_for_stopline
        sr.strip_for_stopline = lambda *a: calls.append(a) or real(*a)
        try:
            self.assertEqual(list(sr.stopline_line_terms("--\n" * 1000, "sql")), [])
            self.assertEqual(calls, [])
            self.assertEqual(terms("-- birthday\nx int\n", "sql"), [])  # the letters are there, in a comment: stripped, no hit
            self.assertEqual(len(calls), 1)
        finally:
            sr.strip_for_stopline = real

    def test_many_unclosed_openers_stay_linear(self):
        """custody's ShipReviewTests input: an unclosed opener must not rescan the rest of the file each time."""
        for kind, text in (("sql", "/* a" * 100000), ("slash", "/* a" * 100000), ("graphql", '"""a' * 60000),
                           ("sql", "x' " * 60000)):
            t0 = time.monotonic()
            out = sr.strip_for_stopline(text, kind)
            self.assertLess(time.monotonic() - t0, 1.0, kind)
            self.assertEqual(len(out), len(text))

    def test_fuzz_line_terms_only_list_members(self):
        rng = random.Random(7)
        alphabet = "abcdefgh_ \n\r'\"`/*-#@()$\\éДcreditcardbirthday"
        fields = set(sr.STOPLINE_FIELDS)
        for _ in range(1500):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 200)))
            kind = rng.choice(("sql", "slash", "hash", "graphql"))
            for n, ident, t in sr.stopline_line_terms(text, kind):
                self.assertIn(t, fields)
                self.assertGreaterEqual(n, 1)
                self.assertLessEqual(n, text.count("\n") + 1)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FloorTests(unittest.TestCase):
    """The shared stripper removes at least what 0.3.2's and build-decisions main's strippers remove, on the corpus."""

    @classmethod
    def setUpClass(cls):
        cls.release = _load(os.path.join(CUSTODY_SCRIPTS, "custody_scan_0_3_2.py"), "floor_release_0_3_2")
        cls.bd = _load(os.path.join(BD_SCRIPTS, "census_scan.py"), "floor_census_scan")

    def corpus(self):
        roots = [os.path.join(CUSTODY_SCRIPTS, "fixtures"), os.path.join(BD_SCRIPTS, "fixtures"),
                 os.path.join(HERE, "fixtures")]
        exts = (".sql", ".psql", ".pgsql", ".ddl", ".prisma", ".graphql", ".gql", ".py", ".rb", ".ts", ".js")
        for root in roots:
            for path in glob.glob(os.path.join(root, "**", "*"), recursive=True):
                ext = os.path.splitext(path)[1].lower()
                schema = (ext in self.bd.SQL_EXTS or ext in self.bd.SCHEMA_EXTS
                          or self.bd.SCHEMA_NAME_RE.search(os.path.basename(path)))
                if os.path.isfile(path) and path.lower().endswith(exts) and schema:
                    yield path

    @staticmethod
    def idents_by_line(text):
        return [set(sr.IDENT_RE.findall(line)) for line in text.split("\n")]

    def kept(self, text, kind):
        return self.idents_by_line(sr.strip_for_stopline(text, kind))

    def assert_floor(self, path, mine, ref, who):
        for n, (m, r) in enumerate(zip(mine, ref), 1):
            self.assertTrue(m <= r, "%s:%d keeps %s that %s removes" % (path, n, sorted(m - r), who))

    def test_floor_against_0_3_2_and_bd_main(self):
        seen = 0
        for path in self.corpus():
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read().replace("\r\n", "\n")
            kind = sr.stopline_kind(path)
            mine = self.kept(text, kind)
            if kind in ("sql", "slash"):
                strip = self.release._strip_sql_comments if kind == "sql" else self.release._strip_slash_comments
                self.assert_floor(path, mine, self.idents_by_line(strip(text)), "0.3.2")
            ext = os.path.splitext(path)[1].lower()
            bd_lines = []
            for line in text.split("\n"):
                body = self.bd.comment_body(line.strip(), ext)
                bd_lines.append(self.bd.strip_trailing_comment(line, ext) if body is None else "")
            self.assert_floor(path, mine, [set(sr.IDENT_RE.findall(x)) for x in bd_lines], "bd main")
            seen += 1
        self.assertGreater(seen, 5)

    def test_stripping_keeps_length_and_newlines(self):
        for kind in ("sql", "slash", "hash", "graphql"):
            text = "a 'b' \"c\" -- d\n/* e\nf */ # g // h\n"
            out = sr.strip_for_stopline(text, kind)
            self.assertEqual(len(out), len(text))
            self.assertEqual([i for i, c in enumerate(out) if c == "\n"], [i for i, c in enumerate(text) if c == "\n"])


class NeverOpenTests(unittest.TestCase):
    def test_never_open_rules_equal_frozen_0_3_2s(self):
        release = _load(os.path.join(CUSTODY_SCRIPTS, "custody_scan_0_3_2.py"), "never_open_release_0_3_2")
        self.assertEqual(set(sr.NEVER_OPEN_DIRS), release.NEVER_OPEN_DIRS)
        self.assertEqual(set(sr.NEVER_OPEN_DIR_PAIRS), release.NEVER_OPEN_DIR_PAIRS)
        self.assertEqual(set(sr.NEVER_OPEN_FILES), release.NEVER_OPEN_FILES)
        self.assertEqual((sr.NEVER_OPEN_FILE_RE.pattern, sr.NEVER_OPEN_FILE_RE.flags),
                         (release.NEVER_OPEN_FILE_RE.pattern, release.NEVER_OPEN_FILE_RE.flags))

    def test_never_open_sets_are_frozen(self):
        for name in ("NEVER_OPEN_DIRS", "NEVER_OPEN_DIR_PAIRS", "NEVER_OPEN_FILES"):
            self.assertIsInstance(getattr(sr, name), frozenset, name)


class NeverOpenProseTests(unittest.TestCase):
    def test_prose_names_every_instruction_file_and_folder_the_code_skips(self):
        files, folders = set(sr.NEVER_OPEN_INSTRUCTION_FILES), set(sr.NEVER_OPEN_INSTRUCTION_FOLDERS)
        for name in sr.NEVER_OPEN_FILES:
            self.assertIn(name, files)
        for d in sr.NEVER_OPEN_DIRS:
            self.assertIn(d + "/", folders)
        for parent, child in sr.NEVER_OPEN_DIR_PAIRS:
            self.assertIn("%s/%s/" % (parent, child), folders)

    def test_every_prose_file_name_is_skipped_by_the_code(self):
        for name in sr.NEVER_OPEN_INSTRUCTION_FILES:
            probe = name.replace("*", "x")
            self.assertTrue(probe in sr.NEVER_OPEN_FILES or sr.NEVER_OPEN_FILE_RE.match(probe), name)


class MistakeMeaningsTests(unittest.TestCase):
    def test_five_meanings_label_then_sentence(self):
        self.assertEqual([label for label, _ in sr.MISTAKE_MEANINGS], [
            "card details the app handles itself",
            "money held or moved for other people",
            "health data, or other people's sensitive data (fields such as ID numbers, dates of birth, passports)",
            "real scale, or a contract that needs the app to stay up",
            "money, and it is not clear which kind"])
        for _label, sentence in sr.MISTAKE_MEANINGS:
            self.assertTrue(sentence.endswith(".") and '"' not in sentence, sentence)


class KeySentenceTests(unittest.TestCase):
    def test_key_sentence_is_pinned(self):
        # Lowercase, no full stop: both rules use it mid-sentence after "say in one line:" / "answer with one line:".
        self.assertEqual(sr.KEY_SENTENCE, "assume it is exposed, and replace it now with a new one")

    def test_key_sentence_keeps_scopes_one_safety_step(self):
        with open(os.path.join(HERE, "SCOPE.md"), encoding="utf-8") as fh:
            scope = fh.read()
        self.assertIn('"replace it now"', scope)
        self.assertIn("replace it now", sr.KEY_SENTENCE)


class Python38Tests(unittest.TestCase):
    def test_no_annotations_so_old_pythons_reach_each_scripts_version_check(self):
        with open(sr.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.assertIsNone(node.returns, node.name)
                for a in node.args.args + node.args.kwonlyargs:
                    self.assertIsNone(a.annotation, node.name)
            self.assertNotIsInstance(node, ast.AnnAssign)

    def test_standard_library_only(self):
        with open(sr.__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module.split(".")[0])
        self.assertTrue(names <= {"os", "re"}, names)


if __name__ == "__main__":
    unittest.main()
