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
# Per app, never a whole-app exemption. Format: {"app": "...", "path": "...", "line": N, "field": "...", "reason": "..."}
# New hints are allowed: since 0.6.3 (S-062) the shared matcher adds fields written as one word (creditcard).
HINT_EXCEPTIONS = [
    {"app": "corpus", "path": "prisma/schema/patient.prisma", "line": 7, "field": "medical",
     "reason": "main read a line inside a /* */ comment as a field"},
    {"app": "corpus", "path": "supabase/migrations/004_notes.sql", "line": 4, "field": "medical",
     "reason": "main read a line inside a /* */ comment as a field"},
    {"app": "corpus", "path": "db/schema.js", "line": 6, "field": "passport",
     "reason": "main read a word inside a quoted value ('a passport photo') as a field"},
    {"app": "corpus", "path": "db/schema.rb", "line": 7, "field": "medical",
     "reason": "main read a word inside a quoted value (\"no medical notes yet\") as a field"},
    {"app": "shared-stopline-app", "path": "db/schema.sql", "line": 11, "field": "medical",
     "reason": "main read a line inside a /* */ comment as a field (the S-062 agreement app's negative case)"},
    {"app": "shared-stopline-app", "path": "prisma/schema.prisma", "line": 8, "field": "medical",
     "reason": "main read a line inside a /* */ comment as a field (the S-062 agreement app's negative case)"},
]


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
        hints = lambda r: {(h["path"], h["line"], h["field"]) for h in r["stopline_hints"]}
        allowed = lambda app: {(e["path"], e["line"], e["field"]) for e in HINT_EXCEPTIONS if e["app"] == app}
        for app in apps:
            theirs_line, mine_line = scan(script, app), scan(SCRIPT, app)
            name = os.path.basename(app)
            # Every hint main lists, the branch lists too (S-062: new hints are allowed, none lost).
            lost = sorted(hints(theirs_line) - hints(mine_line) - allowed(name))
            self.assertEqual(lost, [], "main reports these stop-line hints on %s and the branch does not: %r" % (name, lost))
            self.assertTrue(set(theirs_line["warnings"]) <= set(mine_line["warnings"]), name)
            theirs_line.pop("version"), mine_line.pop("version")
            # 0.5.1 adds the sample-key places after the findings are trimmed; 0.6.3 adds stop-line hints.
            # Everything else stays main's: candidates, their order, totals and partial reasons.
            for line in (theirs_line, mine_line):
                for key in ("demo_keys", "demo_keys_trimmed", "stopline_hints", "warnings"):
                    line.pop(key, None)
            self.assertEqual(dumps(mine_line), dumps(theirs_line), "census line differs from main on %s" % name)
        lost_hints = sorted(hints(main_result) - hints(self.uncapped) - allowed("corpus"))
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


def pay_listings(result):
    """Everything the payment section lists, as comparable identity keys."""
    out = {("writer", w["path"], w["line"], w["field"], w["where"]) for w in result["writers"]}
    out |= {("webhook", h["path"], h["line"], h["signature"]) for h in result["webhooks"]}
    out |= {("client-write", c["path"], c["line"], c["field"]) for c in result["client_writes"]}
    out |= {("price-constant", p["path"], p["line"]) for p in result["price_pairs"]["constants"]}
    out |= {("price-id", p["path"], p["line"]) for p in result["price_pairs"]["payment_ids"]}
    return out


# Payment listings main had that the branch may drop, or new ones the branch may add, each with the reason.
# Format: {"key": [...identity key...], "reason": "..."}
PAY_RECALL_EXCEPTIONS = []
PAY_NEW_ALARM_EXCEPTIONS = []


class PaymentSectionTests(unittest.TestCase):
    """The payment section is new in 0.5.0: gated by seeded positives and labeled negatives on
    fixtures/payments, and by main vs branch once main ships the section."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="census-pay-")
        cls.expected = load_expected()["sections"]["payment"]
        cls.repo = os.path.join(cls.tmp, cls.expected["app"])
        shutil.copytree(os.path.join(FIXTURES, cls.expected["app"]), cls.repo)
        cls.result = scan(SCRIPT, cls.repo, "--section", "payment")
        cls.listed = pay_listings(cls.result)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_seeded_listed(self):
        """protects=every seeded writer, handler verdict, browser write and price pair is listed;
        fails_when=one is missing or carries another kind or verdict;
        no_claim=only as good as the fixture."""
        missing = [tuple(s["key"]) for s in self.expected["seeded"] if tuple(s["key"]) not in self.listed]
        self.assertEqual(missing, [])
        self.assertEqual(self.result["coverage"], "complete")

    def test_negatives_not_listed(self):
        """protects=handler modules, checks one import away, alias imports, payment-company calls, comments and
        server files stay out;
        fails_when=a negative path is listed under its kind (and verdict or line, when the negative names one);
        no_claim=noise in paths the fixture does not label is not measured."""
        for n in self.expected["negatives"]:
            hits = [k for k in self.listed if k[0] == n["kind"] and k[1] == n["path"]
                    and ("line" not in n or k[2] == n["line"])
                    and ("signature" not in n or k[3] == n["signature"])]
            self.assertEqual(hits, [], "%s: %s" % (n["path"], n["why"]))

    def test_never_worse_than_main(self):
        """protects=no later version drops a payment listing or adds a new one (a handler newly called
        not-found is a new listing) without a listed reason;
        fails_when=main's section and the branch's differ with no exception;
        no_claim=skipped (visibly) while main has no payment section (before 0.5.0 merges)."""
        script = main_script(self.tmp)
        if script is None:
            self.skipTest("main helper not found; the census differential reports this")
        parent, name = os.path.split(self.repo)
        proc = subprocess.run([sys.executable, "-I", script, "--repo", name, "--section", "payment"],
                              cwd=parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        theirs = json.loads(proc.stdout.decode("utf-8").strip().split("\n")[0])
        if not theirs.get("ok") and theirs.get("error") == "usage":
            print("SKIPPED: main has no payment section yet")
            self.skipTest("main has no payment section yet")
        main_listed = pay_listings(theirs)
        lost = sorted(main_listed - self.listed - {tuple(e["key"]) for e in PAY_RECALL_EXCEPTIONS})
        self.assertEqual(lost, [], "main lists these and the branch does not: %r" % lost)
        new = sorted(self.listed - main_listed - {tuple(e["key"]) for e in PAY_NEW_ALARM_EXCEPTIONS})
        self.assertEqual(new, [], "the branch lists these and main does not (add each with a reason): %r" % new)


# Every warning the helper prints on a fixture app or a scaffolded eval case, by exact case, with its reason
# (S-059, C1/C14). Any warning not listed here fails CI, and so does an entry that no longer fires.
# Key: [where, app folder, job, [library, path, line], ...] in the helper's place order.
WARN_NEW_ALARMS = [
    {"key": ["evals/fixtures/notewell", ".", "http", ["axios", "src/lib/notesClient.ts", 1],
             ["ky", "src/lib/syncClient.ts", 1]],
     "reason": "seeded: notewell sends requests with axios and with ky (warnings-app)"},
    {"key": ["evals/warnings-crowded/cartwheel", ".", "http", ["axios", "src/lib/net/feed.ts", 1],
             ["ky", "src/lib/net/upload.ts", 1]],
     "reason": "seeded by the warnings-crowded scaffold (two warnings on the crowded app)"},
    {"key": ["evals/warnings-crowded/cartwheel", ".", "state", ["zustand", "src/lib/store/sidebar.ts", 1],
             ["jotai", "src/lib/store/theme.ts", 1]],
     "reason": "seeded by the warnings-crowded scaffold (two warnings on the crowded app)"},
    {"key": ["evals/warnings-app/notewell", ".", "http", ["axios", "src/lib/notesClient.ts", 1],
             ["ky", "src/lib/syncClient.ts", 1]],
     "reason": "seeded: the warnings-app scaffold copies notewell"},
]
# Warnings main prints that the branch may stop printing, each with the reason main was wrong. Same key shape.
WARN_RECALL_EXCEPTIONS = []


def warn_keys(where, result):
    return {(where, f["app"], f["job"]) + tuple((p["name"], p["path"], p["line"]) for p in f["places"])
            for f in result["findings"]}


def norm_key(key):
    return tuple(key[:3]) + tuple(tuple(p) for p in key[3:])


def warning_apps(tmp):
    """(where, app dir) for every unit fixture, every eval fixture and every eval case as its scaffold builds it."""
    out = [("fixtures/" + n, os.path.join(FIXTURES, n)) for n in sorted(os.listdir(FIXTURES))
           if os.path.isdir(os.path.join(FIXTURES, n))]
    out += [("evals/fixtures/" + n, os.path.join(EVAL_FIXTURES, n)) for n in sorted(os.listdir(EVAL_FIXTURES))
            if os.path.isdir(os.path.join(EVAL_FIXTURES, n))]
    for evals in ("evals", "evals-no-search"):
        root = os.path.join(PLUGIN_DIR, evals)
        for case in sorted(os.listdir(root)):
            sc = os.path.join(root, case, "scaffold.sh")
            if not os.path.isfile(sc):
                continue
            work = os.path.join(tmp, evals, case)
            os.makedirs(work)
            subprocess.run(["bash", sc], cwd=work, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out += [("%s/%s/%s" % (evals, case, n), os.path.join(work, n)) for n in sorted(os.listdir(work))
                    if os.path.isdir(os.path.join(work, n))]
    return out


def unlisted_warnings(found):
    return sorted(found - {norm_key(e["key"]) for e in WARN_NEW_ALARMS})


class WarningsSectionTests(unittest.TestCase):
    """The warnings section is new in 0.7.0 (S-059): every warning on a fixture or scaffolded eval case is listed
    in WARN_NEW_ALARMS with its reason, and main vs branch once main ships the section."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="census-warn-")
        cls.apps = warning_apps(cls.tmp)
        cls.found = set()
        for where, path in cls.apps:
            cls.found |= warn_keys(where, scan(SCRIPT, path, "--section", "warnings"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_warning_is_listed(self):
        """protects=C1/C14: a release never adds a warning to a fixture without saying why;
        fails_when=the helper prints a warning WARN_NEW_ALARMS does not list;
        no_claim=real apps (the F-6 sample measured those)."""
        self.assertEqual(unlisted_warnings(self.found), [])

    def test_every_listed_warning_still_fires(self):
        """protects=never-miss: each seeded warning is still found;
        fails_when=an entry in WARN_NEW_ALARMS is no longer printed;
        no_claim=places the fixtures do not seed."""
        stale = sorted({norm_key(e["key"]) for e in WARN_NEW_ALARMS} - self.found)
        self.assertEqual(stale, [])

    def test_planted_warning_turns_the_gate_red(self):
        """protects=the gate itself (C1 mutation): one more library used in a fine fixture is caught;
        fails_when=a planted second HTTP library in notewell-quiet passes unlisted;
        no_claim=other plants."""
        repo = os.path.join(self.tmp, "planted", "notewell-quiet")
        shutil.copytree(os.path.join(EVAL_FIXTURES, "notewell-quiet"), repo)
        with open(os.path.join(repo, "src", "lib", "syncClient.ts"), "w", encoding="utf-8") as fh:
            fh.write("import ky from 'ky'\n\nexport const pushNotes = (n: unknown[]) => ky.post('/n', { json: n })\n")
        planted = warn_keys("evals/fixtures/notewell-quiet", scan(SCRIPT, repo, "--section", "warnings"))
        self.assertEqual(len(unlisted_warnings(self.found | planted)), 1)

    def test_never_worse_than_main(self):
        """protects=no later version drops a warning main prints, or prints a new one, without a listed reason;
        fails_when=main's warnings and the branch's differ with no exception;
        no_claim=skipped (visibly) while main has no warnings section (before 0.7.0 merges)."""
        script = main_script(self.tmp)
        if script is None:
            self.skipTest("main helper not found; the census differential reports this")
        theirs = set()
        for where, path in self.apps:
            parent, name = os.path.split(path)
            proc = subprocess.run([sys.executable, "-I", script, "--repo", name, "--section", "warnings"],
                                  cwd=parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
            result = json.loads(proc.stdout.decode("utf-8").strip().split("\n")[0])
            if not result.get("ok") and result.get("error") == "usage":
                print("SKIPPED: main has no warnings section yet")
                self.skipTest("main has no warnings section yet")
            theirs |= warn_keys(where, result)
        lost = sorted(theirs - self.found - {norm_key(e["key"]) for e in WARN_RECALL_EXCEPTIONS})
        self.assertEqual(lost, [], "main prints these and the branch does not: %r" % lost)
        new = unlisted_warnings(self.found - theirs)
        self.assertEqual(new, [], "the branch prints these and main does not (add each with a reason): %r" % new)


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
