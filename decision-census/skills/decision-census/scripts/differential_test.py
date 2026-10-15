"""Never worse than main: the helper judges, so every change is compared with the released one.

Three gates, all on fixtures/corpus (python 3.9, unittest only):
1. Never-miss: every seeded decider in expected.json is listed, capped and uncapped.
2. Noise, absolute: each negative file lists at most its max_listed (0 by default), unless
   EXCEPTIONS names it with the reason. This applies from the first release on.
3. Main vs branch (once origin/main ships decision-census), uncapped: the branch lists every
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
# scripts -> decision-census (skill) -> skills -> decision-census (plugin) -> repo root
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
REPO_ROOT = os.path.dirname(PLUGIN_DIR)
MAIN_REF = os.environ.get("CENSUS_MAIN_REF", "origin/main")
MAIN_SCRIPT_PATH = "decision-census/skills/decision-census/scripts/census_scan.py"

# Negative files that may list more than max_listed, each with the reason the expectation was wrong.
# Format: {"path": "src/...", "max_listed": N, "reason": "..."}
EXCEPTIONS = []

# Triples main listed that the branch may stop listing, each with the reason main was wrong.
# Format: {"path": "...", "line": N, "type": "...", "reason": "..."}
RECALL_EXCEPTIONS = []

# Triples the branch lists that main did not, each with the reason main was wrong to miss them.
# A release that widens the vocabulary lists every new hit here (that is the point of the list).
NEW_ALARM_EXCEPTIONS = []


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


def main_script(tmp):
    """Export main's helper with git archive. Returns its path, or None when main has none."""
    try:
        subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "--verify", MAIN_REF],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        listing = subprocess.run(["git", "-C", REPO_ROOT, "ls-tree", "--name-only", MAIN_REF, MAIN_SCRIPT_PATH],
                                 check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    except (subprocess.CalledProcessError, OSError):
        return None
    if not listing:
        return None
    archive = os.path.join(tmp, "main.tar")
    subprocess.run(["git", "-C", REPO_ROOT, "archive", "-o", archive, MAIN_REF, "decision-census/skills/decision-census/scripts/"],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = os.path.join(tmp, "main")
    os.makedirs(out)
    subprocess.run(["tar", "-xf", archive, "-C", out], check=True)
    return os.path.join(out, MAIN_SCRIPT_PATH)


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
        no_claim=skipped (visibly) while origin/main has no decision-census helper; fails in CI when origin/main
        cannot be resolved once this branch ships the helper, so a shallow checkout never passes silently."""
        script = main_script(self.tmp)
        if script is None:
            if os.environ.get("CI") and not main_ref_resolves():
                self.fail("%s cannot be resolved in CI; check out with fetch-depth: 0" % MAIN_REF)
            self.skipTest("main has no decision-census helper; compared against expected.json only")
        theirs = triples(scan(script, self.repo, "--uncapped"))
        mine = triples(self.uncapped)
        lost = sorted(theirs - mine - {(e["path"], e["line"], e["type"]) for e in RECALL_EXCEPTIONS})
        self.assertEqual(lost, [], "main lists these and the branch does not: %r" % lost)
        new = sorted(mine - theirs - {(e["path"], e["line"], e["type"]) for e in NEW_ALARM_EXCEPTIONS})
        self.assertEqual(new, [], "the branch lists these and main does not (add each to NEW_ALARM_EXCEPTIONS with a reason): %r" % new)


if __name__ == "__main__":
    unittest.main()
