#!/usr/bin/env python3
"""Never worse than main: the branch's scanner against the released one, on the same inputs.

The released scanner is read from git (CUSTODY_BASELINE_REF, default origin/main). For every input below,
both scanners run with the same patches, and the branch fails if, on any question, it is ever more
permissive than the release ("yes" or "nothing-found" where the release said "no" or "dont-know"), raises a
new alarm (a "no" the release did not give), or clears a partial scan the release flagged. A difference is
allowed only when EXCEPTIONS names that exact case with the reason the release was wrong.

Every input a review finds belongs in CASES.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import custody_scan as branch  # noqa: E402
from custody_scan_test import (  # noqa: E402  (no TestCase with tests is imported, so nothing runs twice)
    FIXTURES, HAVE_GIT, REPO_ROOT, SK, KilledLatePopen, ScanCase, _Reparse,
)

SCANNER_PATH = "custody-check/skills/custody-check/scripts/custody_scan.py"
BASELINE_REF = os.environ.get("CUSTODY_BASELINE_REF", "origin/main")
REQUIRE_BASELINE = os.environ.get("CUSTODY_REQUIRE_BASELINE") == "1"
RANK = {"no": 0, "dont-know": 1, "yes": 2, "nothing-found": 2}

# (case, question or "partial") -> why the release was wrong there. Windows differences are handled below.
TRUNCATED_TAGS = ("output from `for-each-ref refs/tags` that hit the cap proves at least one tag exists; the release counted 0 "
                  "only because the git it killed exited non-zero, so its Q5 'dont-know' was wrong and 'yes' is right")
EXCEPTIONS = dict.fromkeys([("tag list cut at the cap", "q5.code"), ("tag cut mid-name", "q5.code"),
                            ("one tag longer than the cap", "q5.code")], TRUNCATED_TAGS)

# Windows only, and only for a case where the release demonstrably read files short (see release_blind): the release
# opens files in text mode, every CRLF file reads short and is discarded, so its answers there are about nothing.
WINDOWS_REASON = "the release opens files in Windows text mode, reads every CRLF file short and discards it"
WINDOWS_EXCEPTIONS = dict.fromkeys([("fixture never_open", "q1"), ("git history", "q1"), ("git subdir", "q1"),
                                    ("fixture env_names/c", "q1"), ("fixture env_names/c", "q6"),
                                    ("tag list cut at the cap", "q1"), ("tag cut mid-name", "q1"),
                                    ("one tag longer than the cap", "q1"), ("deploy config, no tags, no cap", "q1")], WINDOWS_REASON)


def _load_release():
    try:
        source = subprocess.run(["git", "-C", REPO_ROOT, "show", "%s:%s" % (BASELINE_REF, SCANNER_PATH)],
                                capture_output=True, check=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    folder = tempfile.mkdtemp(prefix="custody release ")
    try:
        path = os.path.join(folder, "custody_scan_release.py")
        with open(path, "wb") as fh:
            fh.write(source)
        spec = importlib.util.spec_from_file_location("custody_scan_release", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # the module lives in memory from here on
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return module


RELEASE = _load_release()


def release_blind(result):
    """Windows evidence that the release read files short and threw them away in this case."""
    return os.name == "nt" and result["stats"]["files_errored"] > 0


def answers(result):
    out = {"partial": result["partial"]}

    def walk(node, prefix):
        for key, value in node.items():
            if isinstance(value, dict) and "answer" in value:
                out[prefix + key] = value["answer"]
            elif isinstance(value, dict):
                walk(value, prefix + key + ".")
    walk(result["questions"], "")
    return out


def worse(case, released, ours, blind=False):
    """Every way the branch is more permissive than the release, or alarms where it did not.

    `blind` is evidence, per case, that the release read files short (release_blind); only then do the Windows
    exceptions apply, and only then may the branch raise an alarm or clear a partial flag the release could not see past.
    """
    problems = []
    for key in sorted(set(released) | set(ours)):
        if (case, key) in EXCEPTIONS or (blind and (case, key) in WINDOWS_EXCEPTIONS):
            continue
        before, after = released.get(key), ours.get(key)
        if key == "partial":
            if before and not after and not blind:
                problems.append("%s: partial cleared" % key)
            continue
        if before == after:
            continue
        if after == "no" and before != "no":
            if not blind:  # WINDOWS_REASON: an alarm the release missed only because it read nothing
                problems.append("%s: new alarm (release %r)" % (key, before))
        elif before in RANK and after in RANK:
            if RANK[after] > RANK[before]:
                problems.append("%s: more permissive (%r -> %r)" % (key, before, after))
        else:
            problems.append("%s: %r -> %r" % (key, before, after))
    return problems


def _tags(case, n):
    case.write("vercel.json", "{}\n")  # a deploy config, so Q5 reaches its tags rule
    case.init_repo(commits=1)
    for i in range(n):
        case.git("tag", "t%03d" % i)


def _long_packed_tag(case):
    case.write("vercel.json", "{}\n")
    case.init_repo(commits=1)
    head = case.git("rev-parse", "HEAD").stdout.strip()
    with open(os.path.join(case.repo, ".git", "packed-refs"), "w", newline="\n") as fh:
        fh.write("# pack-refs with: peeled fully-peeled sorted \n%s refs/tags/t%s\n" % (head, "x" * 230))


def _reparse_on(suffix):
    real_lstat = os.lstat

    def lstat(path, *a, **kw):
        st = real_lstat(path, *a, **kw)
        return _Reparse(st) if str(path).replace(os.sep, "/").endswith(suffix) else st
    return lstat


def _limit(n):
    return lambda module: [mock.patch.object(module, "GIT_OUTPUT_LIMIT", n), mock.patch.object(module.subprocess, "Popen", KilledLatePopen)]


# name -> (needs git, setup(case) -> repo or None, patches(module) -> [context managers])
CASES = {
    "fixture seeded-app": (False, lambda c: c.copy_fixture("seeded-app"), None),
    "fixture never_open": (False, lambda c: c.copy_fixture("never_open"), None),
    "fixture excludes": (False, lambda c: c.copy_fixture("excludes"), None),
    "crlf server key": (False, lambda c: c.write("src/api/route.ts", ('const k = "%s";\r\nexport default k;\r\n' % SK).encode(), binary=True), None),
    "crlf client code": (False, lambda c: c.write("src/components/A.tsx", 'import React from "react";\r\nexport const A = () => null;\r\n'.encode(), binary=True), None),
    "git history": (True, lambda c: (c.write("vercel.json", "{}\n"), c.init_repo(commits=12, tag="v1")), None),
    "git subdir": (True, lambda c: (c.write("apps/web/vercel.json", "{}\n"), c.init_repo(commits=12)) and os.path.join(c.repo, "apps", "web"), None),
    "tag list cut at the cap": (True, lambda c: _tags(c, 40), _limit(512)),
    "tag cut mid-name": (True, lambda c: _tags(c, 40), _limit(30 * len("refs/tags/t000\n") + len("refs/tag"))),
    "one tag longer than the cap": (True, _long_packed_tag, _limit(200)),
    "deploy config, no tags, no cap": (True, lambda c: (c.write("vercel.json", "{}\n"), c.init_repo(commits=3)), None),  # a floor must never apply here
    "junction on .git/refs (simulated)": (True, lambda c: c.init_repo(commits=3), lambda m: [mock.patch.object(m.os, "lstat", _reparse_on("/.git/refs"))]),
    "junction on .git (simulated)": (True, lambda c: c.init_repo(commits=3), lambda m: [mock.patch.object(m.os, "lstat", _reparse_on(".git"))]),
}
for _name in sorted(os.listdir(os.path.join(FIXTURES, "env_names"))):
    CASES["fixture env_names/" + _name] = (False, (lambda n: lambda c: c.copy_fixture(os.path.join("env_names", n)))(_name), None)


@unittest.skipIf(RELEASE is None and not REQUIRE_BASELINE, "released scanner not reachable at %s" % BASELINE_REF)
class NeverWorseThanMainTests(ScanCase):
    def test_release_was_loaded(self):
        self.assertIsNotNone(RELEASE, "CUSTODY_REQUIRE_BASELINE=1 but %s:%s could not be read" % (BASELINE_REF, SCANNER_PATH))

    def test_every_case(self):
        for name, (needs_git, setup, patches) in CASES.items():
            if needs_git and not HAVE_GIT:
                continue
            with self.subTest(case=name):
                rm_and_recreate(self.repo)
                repo = setup(self)
                repo = repo if isinstance(repo, str) else self.repo
                results, raw = [], []
                for module in (RELEASE, branch):
                    managers = patches(module) if patches else []
                    for m in managers:
                        m.start()
                    try:
                        raw.append(module.scan(repo))
                        results.append(answers(raw[-1]))
                    finally:
                        for m in reversed(managers):
                            m.stop()
                self.assertEqual(worse(name, results[0], results[1], blind=release_blind(raw[0])), [], "%s (release %s, branch %s)" % (name, results[0], results[1]))


def rm_and_recreate(path):
    if os.path.lexists(path):
        from custody_scan_test import rm_tree
        rm_tree(path)
    os.makedirs(path)


class ComparisonRuleTests(unittest.TestCase):
    """The rule itself: a harness that never fails proves nothing."""

    def test_more_permissive_is_caught(self):
        self.assertTrue(worse("x", {"q1": "no"}, {"q1": "nothing-found"}))
        self.assertTrue(worse("x", {"q1": "dont-know"}, {"q1": "yes"}))

    def test_stricter_is_allowed_but_a_new_alarm_is_not(self):
        self.assertEqual(worse("x", {"q1": "nothing-found"}, {"q1": "dont-know"}), [])
        self.assertTrue(worse("x", {"q1": "dont-know"}, {"q1": "no"}))
        self.assertEqual(worse("x", {"q1": "dont-know"}, {"q1": "no"}, blind=True), [])

    def test_clearing_partial_is_caught(self):
        self.assertTrue(worse("x", {"partial": True}, {"partial": False}))
        self.assertEqual(worse("x", {"partial": True}, {"partial": False}, blind=True), [])
        self.assertEqual(worse("x", {"partial": False}, {"partial": True}), [])

    def test_windows_exceptions_need_evidence(self):
        case = ("fixture never_open", "q1")
        self.assertIn(case, WINDOWS_EXCEPTIONS)
        self.assertTrue(worse(case[0], {"q1": "dont-know"}, {"q1": "nothing-found"}))
        self.assertEqual(worse(case[0], {"q1": "dont-know"}, {"q1": "nothing-found"}, blind=True), [])
        self.assertFalse(release_blind({"stats": {"files_errored": 0}}))

    def test_an_unknown_answer_change_is_caught(self):
        self.assertTrue(worse("x", {"q1": "no"}, {"q1": "maybe"}))

    def test_a_listed_exception_is_allowed(self):
        with mock.patch.dict(EXCEPTIONS, {("x", "q1"): "the release was wrong"}):
            self.assertEqual(worse("x", {"q1": "no"}, {"q1": "yes"}), [])


if __name__ == "__main__":
    unittest.main()
