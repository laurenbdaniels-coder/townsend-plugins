"""Never worse than main: the helper judges, so every change is compared with the released one.

Three gates, all on fixtures/corpus (python 3.9, unittest only):
1. Never-miss: every seeded decider in expected.json is listed, capped and uncapped.
2. Noise, absolute: each negative file lists at most its max_listed (0 by default), unless
   EXCEPTIONS names it with the reason. This applies from the first release on.
3. Main vs branch, uncapped (main's helper is found at the build-decisions path or the older
   decision-census path; in CI, finding neither fails the run): the branch lists every
   (path, line, type) main lists anywhere in the corpus, and nothing main does not list, unless
   RECALL_EXCEPTIONS or NEW_ALARM_EXCEPTIONS names that exact triple with the reason main was wrong.

Every input a review finds is added to the corpus and to expected.json.
"""
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPT_DIR, "census_scan.py")
FIXTURES = os.path.join(SCRIPT_DIR, "fixtures")
CORPUS = os.path.join(FIXTURES, "corpus")
EXPECTED = os.path.join(FIXTURES, "expected.json")
# scripts -> build-decisions (skill) -> skills -> build-decisions (plugin) -> repo root
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
REPO_ROOT = os.path.dirname(PLUGIN_DIR)
EVAL_FIXTURES = os.path.join(PLUGIN_DIR, "evals", "fixtures")
MAIN_REF = os.environ.get("CENSUS_MAIN_REF", "origin/main")
# Where main keeps the helper, newest name first. 0.4.0 renamed the plugin; until it merges, main has
# only the old path. Neither found: the comparison skips visibly, and fails under CI.
MAIN_SCRIPT_PATHS = (
    "build-decisions/skills/build-decisions/scripts/census_scan.py",
    "decision-census/skills/decision-census/scripts/census_scan.py",
)

# Negative files that may list more than max_listed, each with the reason the expectation was wrong.
# Format: {"path": "src/...", "max_listed": N, "reason": "..."}
EXCEPTIONS = []

# Triples main listed that the branch may stop listing, each with the reason main was wrong.
# Format: {"path": "...", "line": N, "type": "...", "reason": "..."}
RECALL_EXCEPTIONS = []

# Triples the branch lists that main did not, each with the reason main was wrong to miss them.
# A release that widens the vocabulary lists every new hit here (that is the point of the list).
NEW_ALARM_EXCEPTIONS = []

# Stop-line hints main reported that the branch may drop, with the reason (fewer hints means a missed "Get a person").
# Format: {"path": "...", "line": N, "field": "...", "reason": "..."}
HINT_EXCEPTIONS = []


def dumps(obj):
    return json.dumps(obj, separators=(",", ":"))  # key order kept: the line must match, not just its contents


def load_expected():
    with open(EXPECTED, encoding="utf-8") as f:
        return json.load(f)


def scan(script, repo_dir, *extra):
    parent, name = os.path.split(repo_dir)
    proc = subprocess.run([sys.executable, "-I", script, "--repo", name] + list(extra),
                          cwd=parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    lines = [ln for ln in proc.stdout.decode("utf-8").split("\n") if ln]
    if len(lines) != 1:
        raise AssertionError("helper printed %d lines" % len(lines))
    result = json.loads(lines[0])
    if not result.get("ok"):
        raise AssertionError("helper failed: %r" % result.get("error"))
    return result


def triples(result):
    return {(c["path"], c["line"], c["type"]) for c in result["candidates"]}


def per_file(result):
    return collections.Counter(c["path"] for c in result["candidates"])


def main_ref_resolves():
    try:
        subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "--verify", MAIN_REF],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def main_script(tmp, ref=MAIN_REF, root=REPO_ROOT):
    """Export main's whole scripts folder with git archive, from the first MAIN_SCRIPT_PATHS entry main
    has. Returns the helper's path, or None when main has neither."""
    try:
        subprocess.run(["git", "-C", root, "rev-parse", "--verify", ref],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, OSError):
        return None
    for rel in MAIN_SCRIPT_PATHS:
        try:
            listing = subprocess.run(["git", "-C", root, "ls-tree", "--name-only", ref, rel], check=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
        except (subprocess.CalledProcessError, OSError):
            return None
        if not listing:
            continue
        archive = os.path.join(tmp, "main.tar")
        subprocess.run(["git", "-C", root, "archive", "-o", archive, ref, os.path.dirname(rel) + "/"],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = os.path.join(tmp, "main")
        os.makedirs(out)
        subprocess.run(["tar", "-xf", archive, "-C", out], check=True)
        return os.path.join(out, rel)
    return None


class DifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="census-diff-")
        cls.repo = os.path.join(cls.tmp, "corpus")
        shutil.copytree(CORPUS, cls.repo)
        cls.expected = load_expected()
        cls.capped = scan(SCRIPT, cls.repo)
        cls.uncapped = scan(SCRIPT, cls.repo, "--uncapped")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_never_miss_seeded_deciders(self):
        """protects=every seeded decider is listed (AC3);
        fails_when=any (path, line, type) in expected.json is missing, capped or uncapped;
        no_claim=only as good as the corpus; real apps write decisions the corpus does not."""
        want = {(s["path"], s["line"], s["type"]) for s in self.expected["seeded"]}
        for label, result in (("capped", self.capped), ("uncapped", self.uncapped)):
            missing = sorted(want - triples(result))
            self.assertEqual(missing, [], "%s run missed seeded deciders: %r" % (label, missing))

    def test_negative_files_stay_quiet(self):
        """protects=a helper that lists everything cannot pass by recall alone (AC4);
        fails_when=a negative file lists more than its max_listed and is not in EXCEPTIONS;
        no_claim=noise in files the corpus does not label is not measured here."""
        allowed = {e["path"]: e["max_listed"] for e in EXCEPTIONS}
        counts = per_file(self.uncapped)
        for neg in self.expected["negatives"]:
            cap = allowed.get(neg["path"], neg["max_listed"])
            self.assertLessEqual(counts.get(neg["path"], 0), cap, "%s: %s" % (neg["path"], neg["why"]))

    def test_never_worse_than_main(self):
        """protects=no later version lists fewer seeded deciders, or more noise, than the released one (AC5);
        fails_when=main lists a corpus decider the branch misses, or the branch lists more in a negative file;
        no_claim=skipped (visibly) outside CI when main's helper is not found; in CI, an unresolved main or a
        main with the helper at neither path fails, so a shallow checkout or a rename never passes silently."""
        script = main_script(self.tmp)
        if script is None:
            if os.environ.get("CI"):
                if not main_ref_resolves():
                    self.fail("%s cannot be resolved in CI; check out with fetch-depth: 0" % MAIN_REF)
                self.fail("main helper not found at %s" % ", ".join(MAIN_SCRIPT_PATHS))
            print("SKIPPED: main helper not found at %s" % ", ".join(MAIN_SCRIPT_PATHS))
            self.skipTest("main helper not found at %s" % ", ".join(MAIN_SCRIPT_PATHS))
        main_result = scan(script, self.repo, "--uncapped")
        theirs = triples(main_result)
        mine = triples(self.uncapped)
        lost = sorted(theirs - mine - {(e["path"], e["line"], e["type"]) for e in RECALL_EXCEPTIONS})
        self.assertEqual(lost, [], "main lists these and the branch does not: %r" % lost)
        new = sorted(mine - theirs - {(e["path"], e["line"], e["type"]) for e in NEW_ALARM_EXCEPTIONS})
        self.assertEqual(new, [], "the branch lists these and main does not (add each to NEW_ALARM_EXCEPTIONS with a reason): %r" % new)
        # The census line itself never changes with the new sections: same keys, candidates, order, totals,
        # hints and partial reasons as main, capped, on the corpus and every eval fixture app.
        apps = [self.repo] + sorted(os.path.join(EVAL_FIXTURES, d) for d in os.listdir(EVAL_FIXTURES)
                                    if os.path.isdir(os.path.join(EVAL_FIXTURES, d)))
        for app in apps:
            theirs_line, mine_line = scan(script, app), scan(SCRIPT, app)
            theirs_line.pop("version"), mine_line.pop("version")
            self.assertEqual(dumps(mine_line), dumps(theirs_line), "census line differs from main on %s" % os.path.basename(app))
        hints = lambda r: {(h["path"], h["line"], h["field"]) for h in r["stopline_hints"]}
        lost_hints = sorted(hints(main_result) - hints(self.uncapped) - {(e["path"], e["line"], e["field"]) for e in HINT_EXCEPTIONS})
        self.assertEqual(lost_hints, [], "main reports these stop-line hints and the branch does not: %r" % lost_hints)


def arch_listings(result):
    """Everything the section lists, as comparable identity keys."""
    out = {("signal", s["signal"], s["path"]) for s in result["shape"]}
    out |= {("fact", f["fact"], f["path"]) for f in result["facts"]}
    out |= {("candidate", c["type"], c["path"], c["line"], c["app"]) for c in result["candidates"]}
    return out


# Section listings main had that the branch may drop, or new ones the branch may add, each with the reason.
# Format: {"key": [...identity key...], "reason": "..."}
ARCH_RECALL_EXCEPTIONS = []
ARCH_NEW_ALARM_EXCEPTIONS = []


class ArchitectureSectionTests(unittest.TestCase):
    """The architecture section is new in 0.4.0: gated by seeded positives and labeled negatives on
    fixtures/shapes, and by main vs branch once main ships the section."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="census-arch-")
        cls.expected = load_expected()["sections"]["architecture"]
        cls.repo = os.path.join(cls.tmp, cls.expected["app"])
        shutil.copytree(os.path.join(FIXTURES, cls.expected["app"]), cls.repo)
        cls.result = scan(SCRIPT, cls.repo, "--section", "architecture")
        cls.listed = arch_listings(cls.result)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_seeded_listed_and_advice(self):
        """protects=every seeded signal, fact and flagged decision is listed, and the rule order picks the seeded advice;
        fails_when=one is missing or the advice id differs;
        no_claim=only as good as the fixture."""
        missing = []
        for s in self.expected["seeded"]:
            if "signal" in s:
                key = ("signal", s["signal"], s["path"])
            elif "fact" in s:
                key = ("fact", s["fact"], s["path"])
            else:
                key = ("candidate", s["candidate"], s["path"], s["line"], s["app"])
            if key not in self.listed:
                missing.append(key)
        self.assertEqual(missing, [])
        self.assertEqual(self.result["advice"], self.expected["advice"])
        self.assertEqual(self.result["coverage"], "complete")

    def test_negatives_not_listed(self):
        """protects=wrappers, server files, comments, docs sites and negated workspaces stay out;
        fails_when=a negative path is listed under its kind;
        no_claim=noise in paths the fixture does not label is not measured."""
        for n in self.expected["negatives"]:
            hits = [k for k in self.listed if k[2] == n["path"]
                    and (k[0] == n["kind"] or k[1] == n["kind"])
                    and ("line" not in n or k[3] == n["line"])]
            self.assertEqual(hits, [], "%s: %s" % (n["path"], n["why"]))

    def test_never_worse_than_main(self):
        """protects=no later version lists fewer seeded section findings, or new ones, than the released one;
        fails_when=main's section lists something the branch drops, or the branch adds a listing main lacks,
        with no exception and reason;
        no_claim=skipped (visibly) while main has no architecture section (before 0.4.0 merges)."""
        script = main_script(self.tmp)
        if script is None:
            self.skipTest("main helper not found; the census differential reports this")
        parent, name = os.path.split(self.repo)
        proc = subprocess.run([sys.executable, "-I", script, "--repo", name, "--section", "architecture"],
                              cwd=parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        theirs = json.loads(proc.stdout.decode("utf-8").strip().split("\n")[0])
        if not theirs.get("ok") and theirs.get("error") == "usage":
            print("SKIPPED: main has no architecture section yet")
            self.skipTest("main has no architecture section yet")
        main_listed = arch_listings(theirs)
        lost = sorted(main_listed - self.listed - {tuple(e["key"]) for e in ARCH_RECALL_EXCEPTIONS})
        self.assertEqual(lost, [], "main lists these and the branch does not: %r" % lost)
        new = sorted(self.listed - main_listed - {tuple(e["key"]) for e in ARCH_NEW_ALARM_EXCEPTIONS})
        self.assertEqual(new, [], "the branch lists these and main does not (add each with a reason): %r" % new)


class MainScriptTests(unittest.TestCase):
    """main_script() finds main's helper under either name, and says so when it finds neither."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="census-main-")
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(self.root)
        git = lambda *a: subprocess.run(["git", "-C", self.root] + list(a), check=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        self.git = git

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit(self, rel):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("print('main')\n")
        with open(os.path.join(os.path.dirname(path), "sibling.py"), "w") as f:
            f.write("X = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "m")
        return self.git("rev-parse", "HEAD").stdout.decode().strip()

    def test_new_path(self):
        ref = self.commit(MAIN_SCRIPT_PATHS[0])
        got = main_script(self.tmp, ref=ref, root=self.root)
        self.assertTrue(got.endswith(MAIN_SCRIPT_PATHS[0]) and os.path.isfile(got))
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(got), "sibling.py")), "the whole scripts folder comes along")

    def test_old_path(self):
        ref = self.commit(MAIN_SCRIPT_PATHS[1])
        got = main_script(self.tmp, ref=ref, root=self.root)
        self.assertTrue(got.endswith(MAIN_SCRIPT_PATHS[1]) and os.path.isfile(got))

    def test_neither_path(self):
        ref = self.commit("other/thing.py")
        self.assertIsNone(main_script(self.tmp, ref=ref, root=self.root))


if __name__ == "__main__":
    unittest.main()
