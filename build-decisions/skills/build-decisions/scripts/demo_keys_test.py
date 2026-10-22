"""Tests for the census's sample-key list (`demo_keys`, python 3.9, unittest only).

Supabase's local development setup ships public sample keys, signed with a public secret. Build Decisions
must not call those keys exposed (S-048), and must never quiet any other key. A line is listed only when
every token on it is a verified sample key and nothing else on it looks like a key.

Every test docstring carries its card: protects / fails_when / no_claim.
Tokens are built at test time from the public secret; none is committed.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import census_scan as cs  # noqa: E402
from census_scan_test import run, write  # noqa: E402

# custody-check's pinned release: its JWT shape is the one this census copies.
CUSTODY_RELEASE = os.path.normpath(os.path.join(
    SCRIPT_DIR, "..", "..", "..", "..", "custody-check", "skills", "custody-check", "scripts", "custody_scan_0_3_2.py"))

PUBLIC_SECRET = b"super-secret-jwt-token-with-at-least-32-characters-long"


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def token(claims, secret=PUBLIC_SECRET, header=None):
    head = b64(json.dumps(header or {"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(claims if isinstance(claims, bytes) else json.dumps(claims).encode())
    sig = b64(hmac.new(secret, (head + "." + body).encode(), hashlib.sha256).digest())
    return head + "." + body + "." + sig


SAMPLE_SERVICE = token({"iss": "supabase-demo", "role": "service_role", "exp": 1983812996})
SAMPLE_ANON = token({"iss": "supabase-demo", "role": "anon", "exp": 1983812996})
WRONG_SECRET = token({"iss": "supabase-demo", "role": "service_role", "exp": 1983812996},
                     secret=b"a-different-secret-for-a-real-project-xx")
REAL_ISS = token({"iss": "supabase", "ref": "abcdefghijklmnop", "role": "service_role"})
NO_ISS = token({"role": "service_role"})
LIST_PAYLOAD = token(b'["supabase-demo"]')
NOT_JSON = token(b"not json at all, just bytes!!")
HUGE = token({"iss": "supabase-demo", "role": "service_role", "pad": "x" * 5000})
NAMED_KEY = "sk_live_" + "A1b2C3d4E5f6G7h8I9j0K1l2"


class SampleKeyRuleTests(unittest.TestCase):
    def test_only_a_token_signed_with_the_public_secret_and_labelled_demo_counts(self):
        """protects=only Supabase's public sample keys count as sample keys; fails_when=the rule trusts the
        label alone, checks only the signature, or crashes on odd input; no_claim=none beyond protects"""
        self.assertTrue(cs.is_sample_key(SAMPLE_SERVICE))
        self.assertTrue(cs.is_sample_key(SAMPLE_ANON))
        for bad in (WRONG_SECRET, REAL_ISS, NO_ISS, LIST_PAYLOAD, NOT_JSON, HUGE, "eyJ.not.a-token", "", "a.b.c"):
            self.assertFalse(cs.is_sample_key(bad), bad[:40])

    def test_signed_with_public_secret_but_not_labelled_demo_does_not_count(self):
        """protects=a token needs both the public signature and the demo label; fails_when=the iss check is
        dropped; no_claim=none beyond protects"""
        self.assertFalse(cs.is_sample_key(token({"iss": "supabase", "role": "service_role"})))

    def test_odd_input_never_raises(self):
        """protects=no token text can crash the census; fails_when=an exception escapes the check;
        no_claim=only the inputs listed"""
        for odd in ("eyJ" + "A" * 9000, "eyJ%%%.$$$.###", "eyJhbGciOiJIUzI1NiJ9..", None, 12, b"bytes"):
            self.assertFalse(cs.is_sample_key(odd))

    def test_jwt_shape_matches_custody_release_text(self):
        """protects=the census finds the same token shape custody-check does; fails_when=the copied pattern
        drifts from the pinned release; no_claim=custody's other key checks are not compared"""
        line_re = re.compile(r"^JWT_RE = re\.compile\(.*\)$", re.M)
        with open(CUSTODY_RELEASE, encoding="utf-8") as fh:
            theirs = line_re.search(fh.read())
        with open(os.path.join(SCRIPT_DIR, "census_scan.py"), encoding="utf-8") as fh:
            mine = line_re.search(fh.read())
        self.assertIsNotNone(theirs, "custody release JWT_RE line not found")
        self.assertIsNotNone(mine, "census JWT_RE line not found")
        self.assertEqual(mine.group(0), theirs.group(0))

    def test_review_corpus_lines_are_never_listed(self):
        """protects=never worse than main: anything key-like beside a sample key keeps the line unlisted, so
        it is reported as before; fails_when=a review-found secret shape slips past the line check;
        no_claim=only the shapes listed (each found by the 10/22 review)"""
        for name, line in REVIEW_CORPUS.items():
            self.assertFalse(cs.line_has_only_sample_keys(line), name)

    def test_plain_sample_key_lines_are_still_listed(self):
        """protects=the stricter check still lets the ordinary sample-key lines through (S-048); fails_when=
        the key-like check catches a URL or a variable name; no_claim=the shapes listed"""
        for line in ("  service_role_key TEXT := '%s'; -- full access needed for http request to storage" % SAMPLE_SERVICE,
                     'export const supabase = createClient("http://127.0.0.1:54321", "%s");' % SAMPLE_ANON,
                     'NEXT_PUBLIC_SUPABASE_ANON_KEY="%s"' % SAMPLE_ANON):
            self.assertTrue(cs.line_has_only_sample_keys(line), line[:40])


# Every input a review found (2026-10-22 round 1). Each must stay unlisted: a line that also holds anything
# key-like, or that the census cut short, is reported as before.
SELF_HOSTED = token({"iss": "supabase-demo", "role": "service_role", "exp": 1983812996},
                    secret=b"your-super-secret-jwt-token-with-at-least-32-characters-long")
REVIEW_CORPUS = {
    "hex secret": "k='%s'; enc='%s'" % (SAMPLE_ANON, "a3f9" * 16),
    "lowercase hex 32": "k='%s'; t='%s'" % (SAMPLE_ANON, "0f1e2d3c4b5a69788796a5b4c3d2e1f0"),
    "short password": 'createClient(url, "%s", {pw: "Hunter2Hunter2xyz"})' % SAMPLE_ANON,
    "password field": 'const c = {anon: "%s", password: "hunter2"};' % SAMPLE_ANON,
    "postgres url": '{ anonKey: "%s", db: "postgresql://postgres:Tr0ub4dor3xyz@db.example.supabase.co:5432/postgres" }' % SAMPLE_ANON,
    "stripe webhook secret": 'const k = "%s"; const w = "whsec_abc123def456ghi789";' % SAMPLE_ANON,
    "self-hosted default secret": "const k = '%s';" % SELF_HOSTED,
}


class DemoKeysOutputTests(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp(prefix="census-demo-")
        self.repo = os.path.join(self.parent, "app")
        os.makedirs(self.repo)

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def scan(self, *extra):
        data, line, _ = run(self.parent, "app", *extra)
        return data, line

    def test_sample_keys_in_sql_and_browser_code_are_listed_by_place_only(self):
        """protects=S-048: the chatbot-ui shape (a sample key in a migration) and one in browser code are
        listed; fails_when=the census misses them or prints the token; no_claim=the report itself (eval)"""
        write(self.repo, "supabase/migrations/001_setup.sql",
              "-- setup\nDECLARE\n  service_role_key TEXT := '%s';\n" % SAMPLE_SERVICE)
        write(self.repo, "src/lib/supabase.ts",
              "export const anonKey = \"%s\";\nexport const url = \"http://127.0.0.1:54321\";\n" % SAMPLE_ANON)
        data, line = self.scan()
        self.assertTrue(data["ok"])
        self.assertEqual(sorted((d["path"], d["line"]) for d in data["demo_keys"]),
                         [("src/lib/supabase.ts", 1), ("supabase/migrations/001_setup.sql", 3)])
        self.assertFalse(data["demo_keys_trimmed"])
        self.assertNotIn("eyJ", line)

    def test_other_tokens_and_mixed_lines_are_never_listed(self):
        """protects=never worse than main: a real or look-alike key is never quieted; fails_when=a line with
        a wrong-signature token, a non-demo token, or a second key is listed; no_claim=none beyond protects"""
        write(self.repo, "src/a.ts", "const a = '%s';\n" % WRONG_SECRET)
        write(self.repo, "src/b.ts", "const b = '%s';\n" % REAL_ISS)
        write(self.repo, "src/c.ts", "const c = ['%s', '%s'];\n" % (SAMPLE_SERVICE, REAL_ISS))
        write(self.repo, "src/d.ts", "const d = {k: '%s', s: '%s'};\n" % (SAMPLE_ANON, NAMED_KEY))
        write(self.repo, "src/e.ts", "const e = '%s'; const f = 'Zq8xW3vB7nM2kL9pR4tY6uI1oA5sD0fGhJ';\n" % SAMPLE_ANON)
        write(self.repo, "src/f.ts", "const f = '%s';\n" % HUGE)
        data, line = self.scan()
        self.assertEqual(data["demo_keys"], [])
        self.assertNotIn("eyJ", line)

    def test_keys_present_when_nothing_found(self):
        """protects=the skill's exact key check never sees an optional field; fails_when=demo_keys or
        demo_keys_trimmed is left out of an output without tokens; no_claim=none beyond protects"""
        write(self.repo, "src/x.ts", "export const price = 10;\n")
        data, _ = self.scan()
        self.assertEqual(data["demo_keys"], [])
        self.assertIs(data["demo_keys_trimmed"], False)

    def test_a_line_cut_short_is_never_listed(self):
        """protects=a key past the census's line cut is never quieted; fails_when=the check reads only the
        first 2048 characters; no_claim=none beyond protects"""
        write(self.repo, "supabase/seed.sql", "insert into cfg values ('%s', '%s', '%s');\n"
              % (SAMPLE_SERVICE, "-" * (cs.LINE_CLIP_CHARS + 50), NAMED_KEY))
        data, _ = self.scan()
        self.assertEqual(data["demo_keys"], [])

    def test_list_is_capped_at_twenty_and_says_so(self):
        """protects=a long list is cut with a signal, never silently; fails_when=the 21st entry is dropped
        without demo_keys_trimmed; no_claim=none beyond protects"""
        write(self.repo, "supabase/seed.sql", "".join("select '%s';\n" % SAMPLE_ANON for _ in range(21)))
        data, _ = self.scan()
        self.assertEqual(len(data["demo_keys"]), cs.MAX_DEMO_KEYS)
        self.assertEqual(cs.MAX_DEMO_KEYS, 20)
        self.assertIs(data["demo_keys_trimmed"], True)

    def test_sections_carry_no_demo_keys(self):
        """protects=the architecture and payment lines stay exactly as on main; fails_when=a section output
        gains the census-only fields; no_claim=the differential test compares the full lines"""
        write(self.repo, "supabase/migrations/001_setup.sql", "select '%s';\n" % SAMPLE_SERVICE)
        for section in ("architecture", "payment"):
            data, _ = self.scan("--section", section)
            self.assertNotIn("demo_keys", data)
            self.assertNotIn("demo_keys_trimmed", data)


def _state(n_hits, demo):
    state = cs.State(cs.Options(1, 1, 1, 1.0))
    state.hits["price"] = [(0, "src/p%d.ts" % i, i, "price-literal") for i in range(1, n_hits + 1)]
    state.demo_keys = list(demo)
    return state


DEMO = [{"path": "supabase/migrations/%03d_long_name_for_padding.sql" % i, "line": i} for i in range(20)]


class OutputBudgetTests(unittest.TestCase):
    def _bare_len(self):
        out = cs.build(_state(30, []), False)
        return len(cs.dumps({k: v for k, v in out.items() if not k.startswith("demo_keys")}).encode("utf-8"))

    def _build_with_cap(self, cap):
        old = cs.MAX_OUTPUT_BYTES
        try:
            cs.MAX_OUTPUT_BYTES = cap
            return cs.build(_state(30, DEMO), False)
        finally:
            cs.MAX_OUTPUT_BYTES = old

    def test_sample_key_fields_never_cause_trimming(self):
        """protects=a line that fits on main is never trimmed because of the new fields (never worse than
        main); fails_when=the byte budget counts demo_keys against the findings; no_claim=a synthetic state"""
        cap = self._bare_len() + 5
        out = self._build_with_cap(cap)
        self.assertNotIn("output_trimmed", out["partial_reasons"])
        self.assertEqual(len(out["candidates"]), 30)
        self.assertNotIn("demo_keys", out)  # no room even for an empty list: the fields are left out
        self.assertNotIn("demo_keys_trimmed", out)
        self.assertLessEqual(len(cs.dumps(out).encode("utf-8")), cap)

    def test_sample_keys_shrink_to_fit_and_say_so(self):
        """protects=the line stays within the host's output limit; fails_when=demo_keys push it over, or are
        cut without demo_keys_trimmed; no_claim=a synthetic state"""
        cap = self._bare_len() + 200
        out = self._build_with_cap(cap)
        self.assertNotIn("output_trimmed", out["partial_reasons"])
        self.assertLess(len(out["demo_keys"]), 20)
        self.assertIs(out["demo_keys_trimmed"], True)
        self.assertLessEqual(len(cs.dumps(out).encode("utf-8")), cap)


if __name__ == "__main__":
    unittest.main()
