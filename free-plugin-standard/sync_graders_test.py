"""Tests for sync_graders.py and the never-worse-than-main differential for the shared grader pack.

Run: python3 -m unittest discover -s free-plugin-standard -p '*_test.py' -v
The differential needs PyYAML (CI installs it) and git history with origin/main.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import sync_graders  # noqa: E402

CASE_HEAD = '''schema_version: "1.1"
name: demo
execution:
  prompt: "run it"
graders:
  - name: "skill-fired"
    type: "tool_used"
    tool: "Skill"
    min: 1
'''


def make_repo(cases, exempt=None):
    """A throwaway repo root holding the real pack and one fake free plugin, 'demo-plugin'."""
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'free-plugin-standard'))
    pack = json.load(open(os.path.join(HERE, 'pack.json')))
    pack['plugins'] = {'demo-plugin': {'exempt': exempt or {}}}
    with open(os.path.join(root, 'free-plugin-standard', 'pack.json'), 'w') as fh:
        json.dump(pack, fh)
    for name, text in cases.items():
        d = os.path.join(root, 'demo-plugin', 'evals', name)
        os.makedirs(d)
        with open(os.path.join(d, 'case.yaml'), 'w') as fh:
            fh.write(text)
    return root


def case_path(root, name):
    return os.path.join(root, 'demo-plugin', 'evals', name, 'case.yaml')


def marker(groups):
    return '  # >>> free-plugin-standard: %s\n  # <<< free-plugin-standard\n' % groups


class SyncTest(unittest.TestCase):
    def tearDown(self):
        for root in getattr(self, '_roots', []):
            shutil.rmtree(root, ignore_errors=True)

    def repo(self, cases, exempt=None):
        root = make_repo(cases, exempt)
        self._roots = getattr(self, '_roots', []) + [root]
        return root

    def test_real_repo_is_in_sync(self):
        self.assertEqual(sync_graders.check(ROOT), [])

    def test_sync_fills_an_empty_block_then_check_passes(self):
        root = self.repo({'a': CASE_HEAD + marker('always issues')})
        self.assertNotEqual(sync_graders.check(root), [])
        self.assertEqual(sync_graders.sync(root), [case_path(root, 'a')])
        self.assertEqual(sync_graders.check(root), [])
        text = open(case_path(root, 'a')).read()
        for name in ('std-no-fix-prompt', 'std-no-code-words', 'std-count-line',
                     'std-why-it-matters', 'std-out-of-sync', 'std-check-it'):
            self.assertIn('"%s"' % name, text)

    def test_sync_is_idempotent(self):
        root = self.repo({'a': CASE_HEAD + marker('always')})
        sync_graders.sync(root)
        first = open(case_path(root, 'a')).read()
        self.assertEqual(sync_graders.sync(root), [])
        self.assertEqual(open(case_path(root, 'a')).read(), first)

    def test_hand_edited_block_is_stale(self):
        root = self.repo({'a': CASE_HEAD + marker('always')})
        sync_graders.sync(root)
        p = case_path(root, 'a')
        text = open(p).read().replace('To fix:|', '', 1)
        open(p, 'w').write(text)
        errors = sync_graders.check(root)
        self.assertEqual(len(errors), 1)
        self.assertIn('stale', errors[0])

    def test_case_without_block_or_exemption_fails(self):
        root = self.repo({'a': CASE_HEAD})
        errors = sync_graders.check(root)
        self.assertEqual(len(errors), 1)
        self.assertIn('no free-plugin-standard block', errors[0])

    def test_exempt_case_passes_and_needs_a_reason(self):
        root = self.repo({'a': CASE_HEAD}, exempt={'a': 'stops before any report'})
        self.assertEqual(sync_graders.check(root), [])
        root = self.repo({'a': CASE_HEAD}, exempt={'a': ''})
        self.assertNotEqual(sync_graders.check(root), [])

    def test_exempt_case_must_exist(self):
        root = self.repo({'a': CASE_HEAD + marker('always')}, exempt={'gone': 'old case'})
        sync_graders.sync(root)
        self.assertTrue(any('gone' in e for e in sync_graders.check(root)))

    def test_exempt_case_may_not_also_carry_a_block(self):
        root = self.repo({'a': CASE_HEAD + marker('always')}, exempt={'a': 'why'})
        sync_graders.sync(root)
        self.assertNotEqual(sync_graders.check(root), [])

    def test_block_must_carry_always(self):
        root = self.repo({'a': CASE_HEAD + marker('issues')})
        sync_graders.sync(root)
        self.assertTrue(any('always' in e for e in sync_graders.check(root)))

    def test_unknown_group_is_rejected(self):
        root = self.repo({'a': CASE_HEAD + marker('always extra')})
        self.assertTrue(any('extra' in e for e in sync_graders.check(root)))

    def test_block_must_end_the_file(self):
        root = self.repo({'a': CASE_HEAD + marker('always') + 'context:\n  scaffold_script: x.sh\n'})
        self.assertTrue(any('end' in e for e in sync_graders.check(root)))

    def test_one_block_per_case(self):
        root = self.repo({'a': CASE_HEAD + marker('always') + marker('always')})
        self.assertTrue(any('one' in e for e in sync_graders.check(root)))

    def test_rendered_block_parses_as_yaml_back_to_the_pack(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML not installed')
        root = self.repo({'a': CASE_HEAD + marker('always issues')})
        sync_graders.sync(root)
        graders = yaml.safe_load(open(case_path(root, 'a')))['graders']
        pack = json.load(open(os.path.join(HERE, 'pack.json')))['groups']
        self.assertEqual(graders[1:], pack['always'] + pack['issues'])

    def test_registered_plugin_without_cases_fails(self):
        root = self.repo({})
        self.assertTrue(any('no eval cases' in e for e in sync_graders.check(root)))

    def test_unregistered_plugin_carrying_blocks_fails(self):
        root = self.repo({'a': CASE_HEAD}, exempt={'a': 'why'})
        d = os.path.join(root, 'other-plugin', 'evals', 'b')
        os.makedirs(d)
        with open(os.path.join(d, 'case.yaml'), 'w') as fh:
            fh.write(CASE_HEAD + marker('always'))
        self.assertTrue(any('not registered' in e for e in sync_graders.check(root)))

    def test_main_entry_point_exit_codes(self):
        script = os.path.join(HERE, 'sync_graders.py')
        ok = subprocess.run([sys.executable, script, '--check', '--root', ROOT],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        root = self.repo({'a': CASE_HEAD})
        bad = subprocess.run([sys.executable, script, '--check', '--root', root],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)


# ---------------------------------------------------------------------------
# Never worse than main: the eval suites' regex graders, as released on main and as on this
# branch, scored on the same saved reports (the final message of 441 real decision-census eval
# runs, 0.1.0 to 0.3.1). For every report:
#   1. no check that fails on main passes on the branch (graders compared by pattern, flags and
#      match, so a renamed or moved grader still counts as the same check), and
#   2. no report that passes every regex grader on main fails one on the branch (no new alarm),
#      unless the exact report is listed in ALLOWED with the reason main was wrong, and
#   3. every case on main still exists on the branch.
# ALLOWED excuses only a new alarm, never a lost check, and an entry that no longer excuses
# anything fails the test. Every plugin registered in pack.json needs its corpus file.
# Checked against Python's re: on the saved runs it reproduces all 2,612 regex verdicts the eval
# runner recorded (scored on the last message).
# ---------------------------------------------------------------------------

# A renamed plugin: branch folder -> the folder main keeps it in, until the rename merges. Main's case
# files are read from the old folder, so the comparison runs instead of finding nothing to compare.
RENAMED = {'build-decisions': 'decision-census'}

# The saved reports were printed under the old name. The branch's graders score each one as the
# renamed plugin prints it: only the name changes (title, footer, booking tag), nothing else, so no
# grader is loosened to accept the old name. Main's graders score the saved text as it is.
RENAMED_TEXT = {'build-decisions': (('# Decision census', '# Build decisions'),
                                    ('decision-census v', 'build-decisions v'),
                                    ('src=decision-census', 'src=build-decisions'))}


def as_renamed(plugin, check):
    """Main's check under the branch's name, so a check that only follows the rename is the same check."""
    pattern = check[0]
    for old, new in RENAMED_TEXT.get(plugin, ()):
        pattern = pattern.replace(old, new)
    pattern = pattern.replace('decision-census', 'build-decisions') if plugin in RENAMED else pattern
    return (pattern,) + tuple(check[1:])


def as_branch_prints(plugin, text):
    for old, new in RENAMED_TEXT.get(plugin, ()):
        text = text.replace(old, new)
    return text


def main_folder(plugin, base):
    """The folder main keeps this plugin's evals in: its own name once merged, else the old one."""
    if _git('cat-file', '-e', '%s:%s/evals' % (base, plugin)).returncode == 0:
        return plugin
    return RENAMED.get(plugin, plugin)


def corpora():
    plugins = json.load(open(os.path.join(HERE, 'pack.json')))['plugins']
    return {p: os.path.join(HERE, 'corpus', '%s-reports.jsonl' % p) for p in sorted(plugins)}

# (plugin, case, sha256 of report text[:12]) -> reason main was wrong. A new alarm on a saved report
# needs an entry here; an entry that no longer excuses anything fails the test.
ALLOWED = {
    # #39's 23 entries went when it merged: main now grades those lines itself, so they excused nothing.
    # 0.4.0 (build-decisions) adds the "How your app is built" line and names its unchecked sections in
    # "Not checked"; every saved report predates both, so each one that passes main fails only those.
    ('build-decisions', 'clean-looking-app', '9a598fd4ee39'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.0
    ('build-decisions', 'clean-looking-app', 'b9d641e5388f'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.0
    ('build-decisions', 'clean-looking-app', 'b6c5a9aa7f43'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'clean-looking-app', '4953c662f670'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'fix-request', '6c84326d3b57'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'fix-request', '9bf1f60eb24c'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'fix-request', 'fb1ee3aa7024'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'fix-request', '10d0ad16edb0'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'fix-request', '7d4a8b4568cb'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'fix-request', '9374529175e1'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'hostile-repo', 'd3cdac4b6145'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'hostile-repo', '87c4da89f638'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'hostile-repo', '69eeebbaa3ca'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'seeded-app', '9e40fe32c2d4'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'seeded-app', '142a1731f82d'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'seeded-app', '8d116ba1e1b2'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'seeded-app-crowded', '7a9fcce2f5a2'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'seeded-app-crowded', 'be2958eba0a6'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'seeded-app-crowded', '32db269eec53'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-constant-app', 'd46e0eb99b08'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-constant-app', '34c69d555efa'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-constant-app', 'd9d50db85efe'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-constant-app', '2fda70241773'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-constant-app', 'e8546c5452b3'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-helper-diverges', 'c4abcce93e11'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-helper-diverges', 'a47f52311a07'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'shared-helper-diverges', '7efef89a24d4'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'stopline-app', 'a945ed3ace84'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.1.2
    ('build-decisions', 'stopline-app', '0db560c07bbc'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.1.2
    ('build-decisions', 'stopline-app', '4fee87acdaaf'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.2.0
    ('build-decisions', 'stopline-app', 'd604557778c8'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.2.1
    ('build-decisions', 'stopline-app', '2c48a176dfd5'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.2.1
    ('build-decisions', 'stopline-app', '17593c36be4a'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.2.1
    ('build-decisions', 'stopline-app', '812d2be83106'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.0
    ('build-decisions', 'stopline-app', 'c46a896f0ebd'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.0
    ('build-decisions', 'stopline-app', '206b3ea10e1f'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'stopline-app', '9a22062e9ba6'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'stopline-app', '6b48a8e4a7c6'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'stopline-app', '97aec9e870c0'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'stopline-app', '26246ddffb0e'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
    ('build-decisions', 'stopline-app', 'c0b6556d0f17'): 'pre-0.4.0 report: no "How your app is built" line and the shorter "Not checked" line; both are new in 0.4.0.',  # 0.3.1
}


def _git(*args):
    return subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True)


def _base():
    r = _git('merge-base', 'HEAD', 'origin/main')
    return r.stdout.strip() if r.returncode == 0 else None


def _regex_checks(text):
    import yaml
    out = []
    for g in (yaml.safe_load(text) or {}).get('graders') or []:
        if g.get('type') == 'regex':
            out.append((g['pattern'], g.get('flags', ''), g.get('match', 'contains')))
    return out


def _fails(check, report):
    pattern, flags, match = check
    found = re.search(pattern, report, re.I if 'i' in flags else 0) is not None
    return found if match == 'not_contains' else not found


class NeverWorseThanMainTest(unittest.TestCase):
    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            if os.environ.get('CI'):
                raise
            self.skipTest('PyYAML not installed (CI installs it)')
        self.base = _base()
        if not self.base:
            if os.environ.get('CI'):
                self.fail('no origin/main to compare against')
            self.skipTest('no origin/main')

    def test_every_registered_plugin_has_a_corpus(self):
        for plugin, corpus in corpora().items():
            self.assertTrue(os.path.isfile(corpus), '%s has no corpus at %s' % (plugin, corpus))

    def test_branch_suite_never_worse_than_main(self):
        import hashlib
        problems = []
        compared = 0
        used = set()
        for plugin, corpus in corpora().items():
            reports = [json.loads(l) for l in open(corpus)]
            on_main = main_folder(plugin, self.base)
            main_cases = _git('ls-tree', '-d', '--name-only', '%s:%s/evals' % (self.base, on_main))
            for case in main_cases.stdout.split():
                if _git('cat-file', '-e', '%s:%s/evals/%s/case.yaml' % (self.base, on_main, case)).returncode:
                    continue
                if not os.path.exists(os.path.join(ROOT, plugin, 'evals', case, 'case.yaml')):
                    problems.append('%s/%s: case on main is missing on the branch' % (plugin, case))
            for case in sorted({r['case'] for r in reports}):
                rel = '%s/evals/%s/case.yaml' % (plugin, case)
                old = _git('show', '%s:%s/evals/%s/case.yaml' % (self.base, on_main, case))
                new_path = os.path.join(ROOT, rel)
                if old.returncode != 0:
                    continue  # a case new on the branch has no baseline
                if not os.path.exists(new_path):
                    continue  # reported above
                main_checks = _regex_checks(old.stdout)
                branch_checks = _regex_checks(open(new_path).read())
                for r in (x for x in reports if x['case'] == case):
                    compared += 1
                    text = r['text']
                    key = (plugin, case, hashlib.sha256(text.encode()).hexdigest()[:12])
                    main_failing = {as_renamed(plugin, c) for c in main_checks if _fails(c, text)}
                    branch_failing = {c for c in branch_checks if _fails(c, as_branch_prints(plugin, text))}
                    lost = main_failing - branch_failing
                    if lost:
                        problems.append('%s more permissive on %s %s: %s' % (
                            key, r['version'], case, [c[0][:60] for c in lost]))
                    if not main_failing and branch_failing and key in ALLOWED:
                        used.add(key)
                    elif not main_failing and branch_failing:
                        problems.append('%s new alarm on %s %s: %s' % (
                            key, r['version'], case, [c[0][:60] for c in branch_failing]))
        for key in sorted(set(ALLOWED) - used):
            problems.append('%s: ALLOWED entry excuses nothing; drop it' % (key,))
        self.assertGreater(compared, 400)
        self.assertEqual(problems, [], '\n'.join(problems))


if __name__ == '__main__':
    unittest.main()
