"""Both free plugins find the same extra-risk fields in the same files (S-062).

custody-check and build-decisions share one stop-line field list and matcher (shared/shared_rules.py). This
test runs both plugins' real scripts, the way their SKILL.md files run them, on fixtures/shared-stopline-app/
and checks that they name the same fields in the same schema files, and that both tick the stop-line.

One difference is listed: custody-check also reads browser forms (public/signup.html, name="bday"), and
build-decisions does not. Any other difference fails.

Run: python3 -m unittest discover -s free-plugin-standard -p '*_test.py' -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "shared"))

import shared_rules as sr  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "shared-stopline-app")
CUSTODY = os.path.join(ROOT, "custody-check", "skills", "custody-check", "scripts")
BD = os.path.join(ROOT, "build-decisions", "skills", "build-decisions", "scripts")

# The one listed difference: custody-check reads browser forms; build-decisions reads schema files only.
CUSTODY_ONLY = {"public/signup.html": {"dob"}}

WANT = {
    "db/schema.sql": {"birthday", "credit_card", "birth_date"},
    "prisma/schema.prisma": {"date_of_birth", "credit_card"},
}


def run(script, *args, cwd, stdin=None):
    proc = subprocess.run([sys.executable, "-I", script] + list(args), cwd=cwd, input=stdin, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=120)
    if proc.returncode not in (0, 1):
        raise AssertionError("%s exited %d: %s" % (script, proc.returncode, proc.stderr.decode()[-2000:]))
    return json.loads(proc.stdout.decode().strip().splitlines()[-1])


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class AgreementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="agreement-")
        app = os.path.join(cls.tmp, "app")
        shutil.copytree(FIXTURE, app)
        for cmd in (["init", "-q"], ["add", "."], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
            subprocess.run(["git"] + cmd, cwd=app, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.census = run(os.path.join(BD, "census_scan.py"), "--repo", "app", cwd=cls.tmp)
        cls.scan = run(os.path.join(CUSTODY, "custody_scan.py"), "--repo", "app", cwd=cls.tmp)
        # The verdict on this scan (--scan-json: the same rules as --repo, without scanning a second time).
        cls.verdict = run(os.path.join(CUSTODY, "custody_verdict.py"), "--scan-json", "-",
                          "--answers", "q5_data=no stop_line=none", cwd=cls.tmp, stdin=json.dumps(cls.scan).encode())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def custody_terms(self):
        out = {}
        for e in self.scan["questions"]["q10"]["evidence"]:
            terms = sr.stopline_terms(e["snippet"])
            if terms:
                out.setdefault(e["path"], set()).update(terms)
        return out

    def bd_terms(self):
        out = {}
        for h in self.census["stopline_hints"]:
            out.setdefault(h["path"], set()).add(h["field"])
        return out

    def test_both_scripts_ran(self):
        for name, result in (("census", self.census), ("scan", self.scan), ("verdict", self.verdict)):
            self.assertIs(result.get("ok"), True, (name, result))

    def test_same_fields_in_the_same_files(self):
        custody = self.custody_terms()
        for path, terms in CUSTODY_ONLY.items():
            self.assertEqual(custody.pop(path, None), terms, "the listed difference changed: " + path)
        self.assertEqual(custody, self.bd_terms())
        self.assertEqual(custody, WANT)

    def test_comments_and_quoted_values_never_count(self):
        """Both schema files hold `medical` and `creditcard` only in comments or a quoted value."""
        for terms in list(self.custody_terms().values()) + list(self.bd_terms().values()):
            self.assertNotIn("medical", terms)
        lines = {(h["path"], h["line"]) for h in self.census["stopline_hints"]}
        self.assertFalse(lines & {("db/schema.sql", 9), ("db/schema.sql", 18), ("prisma/schema.prisma", 1)})

    def test_both_tick_the_stop_line(self):
        self.assertTrue(self.census["stopline_hints"])  # build-decisions SKILL.md rule 7: a hint ticks it
        sl = self.verdict["verdict"]["stop_line"]
        self.assertTrue(sl["ticked"])
        self.assertEqual(self.verdict["verdict"]["door"], "get-a-person")
        self.assertEqual(set(sl["fields"]), {"birthday", "birth_date", "credit_card", "date_of_birth", "dob"})
        self.assertFalse(sl["capped"])


if __name__ == "__main__":
    unittest.main()
