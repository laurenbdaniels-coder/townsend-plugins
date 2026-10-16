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
# unless the exact report is listed in ALLOWED with the reason main was wrong.
# Checked against Python's re: on the saved runs it reproduces all 2,612 regex verdicts the eval
# runner recorded (scored on the last message).
# ---------------------------------------------------------------------------

CORPORA = {'decision-census': os.path.join(HERE, 'corpus', 'decision-census-reports.jsonl')}

# (plugin, case, sha256 of report text[:12]) -> reason main was wrong. Every entry is a report from
# a release before the standard (0.3.1): main never graded these lines in these cases. None is a 0.3.1 report.
ALLOWED = {
    ('decision-census', 'fix-request', '3215465e80ef'): '0.1.x predates the report shape: no count, why, out-of-sync or check-it lines, and code words. Main never graded the shape in this case.',  # 0.1.0
    ('decision-census', 'fix-request', '382b29c0804e'): '0.1.x predates the report shape: no count, why, out-of-sync or check-it lines, and code words. Main never graded the shape in this case.',  # 0.1.0
    ('decision-census', 'fix-request', '08bc24989a71'): '0.1.x predates the report shape: no count, why, out-of-sync or check-it lines, and code words. Main never graded the shape in this case.',  # 0.1.0
    ('decision-census', 'fix-request', '1dc21e397b1b'): '0.1.x predates the report shape: no count, why, out-of-sync or check-it lines, and code words. Main never graded the shape in this case.',  # 0.1.0
    ('decision-census', 'fix-request', '8febab23097c'): '0.1.x predates the report shape: no count, why, out-of-sync or check-it lines, and code words. Main never graded the shape in this case.',  # 0.1.0
    ('decision-census', 'fix-request', 'dcba0a915af8'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.1
    ('decision-census', 'fix-request', '54909bf2fcb6'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.1
    ('decision-census', 'fix-request', '3043b45bf8a6'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.1
    ('decision-census', 'fix-request', '4a35677c0251'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.1
    ('decision-census', 'fix-request', '6364b0c3dff1'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.1
    ('decision-census', 'near-miss', '419ed735dd1c'): 'the founder-facing text uses code words ("config"); main had no code-words grader in this case.',  # 0.1.1
    ('decision-census', 'near-miss', '9a125d8d81ad'): 'the founder-facing text uses code words ("config"); main had no code-words grader in this case.',  # 0.1.1
    ('decision-census', 'near-miss', '96ec7c5f8025'): 'the founder-facing text uses code words ("config"); main had no code-words grader in this case.',  # 0.1.1
    ('decision-census', 'fix-request', '5ee71a00ce5f'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.2
    ('decision-census', 'fix-request', 'e84cb1b3b775'): 'same as 0.1.0: pre-standard report shape, ungraded in this case on main.',  # 0.1.2
    ('decision-census', 'stopline-app', 'bd2e7bb93421'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.1.2
    ('decision-census', 'stopline-app', '8b7b55e00e9a'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.1.2
    ('decision-census', 'stopline-app', 'daf7885b0daf'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.1.2
    ('decision-census', 'stopline-app', 'fe884935fb50'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.1.2
    ('decision-census', 'stopline-app', '414592b1a78e'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.2.0
    ('decision-census', 'stopline-app', 'fcc0cc02ff40'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.2.0
    ('decision-census', 'stopline-app', '4cdbe5d2920b'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.2.0
    ('decision-census', 'stopline-app', '85d4d41bc2d1'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.2.0
    ('decision-census', 'stopline-app', '4610bfb777dd'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.2.0
    ('decision-census', 'stopline-app', '4543da4931b0'): 'the stop-line text uses code words ("schema", "config", "route"); main had no code-words grader in this case.',  # 0.2.0
    ('decision-census', 'near-miss', '3fdc6dbb1f30'): 'the founder-facing text uses code words ("config"); main had no code-words grader in this case.',  # 0.2.1
    ('decision-census', 'stopline-app', 'acea6336a74f'): '0.3.0 gave a fix prompt, the gap 0.3.1 closed; main had no fix-prompt grader in this case.',  # 0.3.0
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

    def test_branch_suite_never_worse_than_main(self):
        import hashlib
        problems = []
        compared = 0
        for plugin, corpus in CORPORA.items():
            reports = [json.loads(l) for l in open(corpus)]
            for case in sorted({r['case'] for r in reports}):
                rel = '%s/evals/%s/case.yaml' % (plugin, case)
                old = _git('show', '%s:%s' % (self.base, rel))
                new_path = os.path.join(ROOT, rel)
                if old.returncode != 0 or not os.path.exists(new_path):
                    continue
                main_checks = _regex_checks(old.stdout)
                branch_checks = _regex_checks(open(new_path).read())
                for r in (x for x in reports if x['case'] == case):
                    compared += 1
                    text = r['text']
                    key = (plugin, case, hashlib.sha256(text.encode()).hexdigest()[:12])
                    if key in ALLOWED:
                        continue
                    main_failing = {c for c in main_checks if _fails(c, text)}
                    branch_failing = {c for c in branch_checks if _fails(c, text)}
                    lost = main_failing - branch_failing
                    if lost:
                        problems.append('%s more permissive on %s %s: %s' % (
                            key, r['version'], case, [c[0][:60] for c in lost]))
                    if not main_failing and branch_failing:
                        problems.append('%s new alarm on %s %s: %s' % (
                            key, r['version'], case, [c[0][:60] for c in branch_failing]))
        self.assertGreater(compared, 400)
        self.assertEqual(problems, [], '\n'.join(problems))


if __name__ == '__main__':
    unittest.main()
