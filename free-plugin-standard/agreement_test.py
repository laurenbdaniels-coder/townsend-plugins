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


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class ReviewInputAgreementTests(unittest.TestCase):
    """Inputs review round 2 found: a field word inside a string value. build-decisions main hints both (it drops
    comments only), so the branch keeps that and custody-check agrees with it. Known weakness, in TODOS.md."""

    FILES = {
        "prisma/schema.prisma": 'model Event {\n  id Int @id\n  kind String @default("birthday")\n}\n',
        "db/seed.sql": "CREATE TABLE notes (id int, body text);\n"
                       "INSERT INTO notes (body) VALUES ('Opening line;\nbirthday invitation');\n",
    }
    WANT = {("prisma/schema.prisma", 3, "birthday"), ("db/seed.sql", 3, "birthday")}

    def test_both_plugins_give_the_same_rows(self):
        tmp = tempfile.mkdtemp(prefix="agreement-review-")
        self.addCleanup(shutil.rmtree, tmp, True)
        for rel, body in self.FILES.items():
            path = os.path.join(tmp, "app", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", newline="") as fh:
                fh.write(body)
        census = run(os.path.join(BD, "census_scan.py"), "--repo", "app", cwd=tmp)
        scan = run(os.path.join(CUSTODY, "custody_scan.py"), "--repo", "app", cwd=tmp)
        bd = {(h["path"], h["line"], h["field"]) for h in census["stopline_hints"]}
        custody = {(e["path"], e["line"], t) for e in scan["questions"]["q10"]["evidence"]
                   if e["check"] == "stopline-field" for t in sr.stopline_terms(e["snippet"])}
        self.assertEqual(bd, self.WANT)
        self.assertEqual(custody, self.WANT)


class EvalCopyTests(unittest.TestCase):
    """Each plugin's eval cases build their app from a copy inside the plugin (an eval may copy one plugin folder
    alone). The copies stay byte-equal to the fixture this test uses."""

    def files(self, root):
        out = {}
        for d, _dirs, names in os.walk(root):
            for n in names:
                with open(os.path.join(d, n), "rb") as fh:
                    out[os.path.relpath(os.path.join(d, n), root)] = fh.read()
        return out

    def test_eval_copies_equal_the_fixture(self):
        want = self.files(FIXTURE)
        for plugin in ("custody-check", "build-decisions"):
            copy = os.path.join(ROOT, plugin, "evals", "fixtures", "shared-stopline-app")
            self.assertEqual(self.files(copy), want, plugin)


if __name__ == "__main__":
    unittest.main()
