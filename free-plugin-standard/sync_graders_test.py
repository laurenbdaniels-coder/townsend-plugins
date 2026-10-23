"""Tests for sync_graders.py and the never-worse-than-main differential for the shared grader pack.

Run: python3 -m unittest discover -s free-plugin-standard -p '*_test.py' -v
The differential needs PyYAML (CI installs it) and git history with origin/main.
"""
import functools
import hashlib
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


def make_repo(cases, exempt=None, words=None, omit=None):
    """A throwaway repo root holding the real pack and one fake free plugin, 'demo-plugin'."""
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'free-plugin-standard'))
    pack = json.load(open(os.path.join(HERE, 'pack.json')))
    pack['plugins'] = {'demo-plugin': {'exempt': exempt or {}}}
    if words is not None:
        pack['plugins']['demo-plugin']['words'] = words
    if omit is not None:
        pack['plugins']['demo-plugin']['omit'] = omit
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

    def repo(self, cases, exempt=None, words=None, omit=None):
        root = make_repo(cases, exempt, words, omit)
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

    def _graders(self, root):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML not installed')
        return {g['name']: g for g in yaml.safe_load(open(case_path(root, 'a')))['graders']}

    def test_plugin_words_change_only_that_plugins_risk_line(self):
        """custody-check says "What could go wrong:" where build-decisions says "If they get out of sync:"."""
        root = self.repo({'a': CASE_HEAD + marker('always issues')},
                         words={'std-out-of-sync': 'What could go wrong:'})
        sync_graders.sync(root)
        self.assertEqual(sync_graders.check(root), [])
        got = self._graders(root)
        pack = {g['name']: g for grp in json.load(open(os.path.join(HERE, 'pack.json')))['groups'].values()
                for g in grp}
        self.assertEqual(got['std-out-of-sync']['pattern'], 'What could go wrong:')
        for name, g in pack.items():
            if name != 'std-out-of-sync':
                self.assertEqual(got[name], g, name)
            else:
                self.assertEqual({k: v for k, v in got[name].items() if k != 'pattern'},
                                 {k: v for k, v in g.items() if k != 'pattern'})

    def test_no_words_keeps_the_pack_pattern(self):
        root = self.repo({'a': CASE_HEAD + marker('always issues')})
        sync_graders.sync(root)
        self.assertEqual(self._graders(root)['std-out-of-sync']['pattern'], 'What it means for you:')  # pack default since bd 0.6.0 (G4)

    def test_words_only_for_graders_the_pack_lets_plugins_word(self):
        """A plugin may reword its risk line, never loosen another shared grader."""
        root = self.repo({'a': CASE_HEAD + marker('always issues')}, words={'std-no-fix-prompt': 'nothing'})
        self.assertTrue(any('std-no-fix-prompt' in e for e in sync_graders.check(root)))

    def test_words_must_be_a_plain_label(self):
        # Value (extended: non-string rows 5, None, list): protects=check reports a non-string label as a
        # problem; fails_when=the isinstance guard is dropped and LABEL.fullmatch raises TypeError, so
        # --check crashes instead of naming the bad entry; why_new=the table held only strings;
        # seam=none; no_claim=does not test which non-string types a JSON pack can hold beyond these.
        for bad in ('', '.*', 'what could go wrong', 'If (they)? break:', 'X' * 60 + ':', 5, None, ['A:']):
            root = self.repo({'a': CASE_HEAD + marker('always issues')}, words={'std-out-of-sync': bad})
            self.assertTrue(any('label' in e for e in sync_graders.check(root)), repr(bad))

    def test_bad_words_never_reach_a_case_file(self):
        # Value: protects=sync never writes a plugin's disallowed or malformed words into its graders;
        # fails_when=_scan stops skipping a plugin with bad words, so sync rewrites the block with the
        # loosened pattern (e.g. std-no-fix-prompt -> 'nothing') and a commit could carry it;
        # why_new=the words tests only call check(), which still errors either way; seam=none;
        # no_claim=does not cover a hand edit of the case file, which the stale-block check owns.
        for words in ({'std-no-fix-prompt': 'nothing'}, {'std-out-of-sync': '.*'}):
            root = self.repo({'a': CASE_HEAD + marker('always issues')})
            sync_graders.sync(root)
            before = open(case_path(root, 'a')).read()
            pack_path = os.path.join(root, 'free-plugin-standard', 'pack.json')
            pack = json.load(open(pack_path))
            pack['plugins']['demo-plugin']['words'] = words
            with open(pack_path, 'w') as fh:
                json.dump(pack, fh)
            self.assertEqual(sync_graders.sync(root), [], words)
            self.assertEqual(open(case_path(root, 'a')).read(), before, words)

    # --- 0.6.0: custody-check's report has its own count line and no Check it line (owner answer 4).

    COUNT = r"(?:^|\n)\*\*We found (?:\d+|no) problems? in your code, and [^\n*]+\.\*\*[ \t]*(?=\n|$)"

    def test_a_plugin_may_word_its_count_line_as_a_bold_line(self):
        root = self.repo({'a': CASE_HEAD + marker('always issues')}, words={'std-count-line': self.COUNT})
        sync_graders.sync(root)
        self.assertEqual(sync_graders.check(root), [])
        got = self._graders(root)['std-count-line']
        self.assertEqual(got['pattern'], self.COUNT)
        self.assertEqual((got['match'], got['flags']), ('contains', ''))
        self.assertTrue(re.search(got['pattern'], 'x\n**We found 2 problems in your code, and 4 things your code can\'t tell us.**\n'))

    def test_count_line_words_must_be_a_bold_line_starting_with_a_word(self):
        """Value: protects=a plugin can't turn its count line into a pattern that matches anything;
        fails_when=the shape check is dropped or only checks the label shape."""
        for bad in ('.*', 'What it means for you:', r'(?:^|\n)\*\*.*\.\*\*[ \t]*(?=\n|$)',
                    r'(?:^|\n)\*\*We found', r'\*\*We found [^\n]+\.\*\*[ \t]*(?=\n|$)',
                    r'(?:^|\n)\*\*We found ([^\n]+\.\*\*[ \t]*(?=\n|$)', 5, None,
                    r'(?:^|\n)\*\*We |(?:)|\.\*\*[ \t]*(?=\n|$)', r'(?:^|\n)\*\*We |x|y\.\*\*[ \t]*(?=\n|$)'):
            root = self.repo({'a': CASE_HEAD + marker('always issues')}, words={'std-count-line': bad})
            self.assertTrue(any('std-count-line' in e for e in sync_graders.check(root)), repr(bad))

    def test_risk_line_words_are_still_a_plain_label(self):
        root = self.repo({'a': CASE_HEAD + marker('always issues')}, words={'std-out-of-sync': self.COUNT})
        self.assertTrue(any('label' in e for e in sync_graders.check(root)))

    def test_omit_drops_only_that_grader_with_a_reason(self):
        root = self.repo({'a': CASE_HEAD + marker('always issues')}, omit={'std-check-it': 'says what is broken, not what to do'})
        sync_graders.sync(root)
        self.assertEqual(sync_graders.check(root), [])
        got = self._graders(root)
        self.assertNotIn('std-check-it', got)
        for name in ('std-no-fix-prompt', 'std-no-code-words', 'std-count-line', 'std-why-it-matters', 'std-out-of-sync'):
            self.assertIn(name, got, name)

    def test_omit_only_for_omittable_graders_and_only_with_a_reason(self):
        """Value: protects=no plugin can drop the no-fix or no-code-words check, or drop one silently;
        fails_when=omit is not checked against the pack's omittable list, or an empty reason passes."""
        for omit in ({'std-no-fix-prompt': 'why'}, {'std-no-code-words': 'why'}, {'std-why-it-matters': 'why'},
                     {'std-check-it': ''}, {'std-check-it': None}, {'nonesuch': 'why'}):
            root = self.repo({'a': CASE_HEAD + marker('always issues')}, omit=omit)
            self.assertTrue(any('omit' in e for e in sync_graders.check(root)), omit)

    def test_bad_omit_never_reaches_a_case_file(self):
        root = self.repo({'a': CASE_HEAD + marker('always issues')})
        sync_graders.sync(root)
        before = open(case_path(root, 'a')).read()
        pack_path = os.path.join(root, 'free-plugin-standard', 'pack.json')
        pack = json.load(open(pack_path))
        pack['plugins']['demo-plugin']['omit'] = {'std-no-fix-prompt': 'why'}
        with open(pack_path, 'w') as fh:
            json.dump(pack, fh)
        self.assertEqual(sync_graders.sync(root), [])
        self.assertEqual(open(case_path(root, 'a')).read(), before)

    def test_real_pack_protects_the_no_fix_line(self):
        pack = json.load(open(os.path.join(HERE, 'pack.json')))
        self.assertNotIn('std-no-fix-prompt', pack.get('omittable', []))
        self.assertNotIn('std-no-code-words', pack.get('omittable', []))
        self.assertNotIn('std-no-fix-prompt', pack['plugin_words'])
        self.assertNotIn('std-no-code-words', pack['plugin_words'])

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
#   2. no report that passes every regex grader on main fails one on the branch (no new alarm), and
#   3. every case on main still exists on the branch,
# unless the exact check on the exact report is listed in ALLOWED with the reason main was wrong,
# or (for rule 2 only) the check is a release's new or reworded grader listed in NEW_GRADERS and the
# report was printed by an older version.
# Every plugin registered in pack.json needs its corpus file.
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


# A fixed report line a release rewords on purpose: main's whole pattern -> the branch's, with the reason.
# Main's check then counts as the branch's check, so a saved report that fails both is not "looser", and
# one the branch passes is still caught. Only exact whole patterns are swapped.
REWORDED = {
    'custody-check': (
        ('(?:^|\\n)\\*\\*Your app has \\d+ [^\\n*]+\\.\\*\\*[ \\t]*(?=\\n|$)', '(?:^|\\n)\\*\\*We found (?:\\d+|no) problems? in your code, and [^\\n*]+\\.\\*\\*[ \\t]*(?=\\n|$)',
         'custody-check 0.6.0 words its count line "We found N problems in your code" (owner answer 3, pack.json words).'),
        ('What could go wrong:', 'What it means for you:',
         'custody-check 0.6.0 names its risk line "What it means for you:" (plan 1c, pack.json words).'),
        ('Not checked: the running app', "We also can't see your live site, your hosting and database dashboards, or settings stored outside your code\\. Not found does not mean it isn't there\\.",
         'custody-check 0.6.0 says the fixed not-checked line in plain words (plan 1e).'),
    ),
    'build-decisions': (
        (r"Not checked: [^\n]*This version also does not check payments, screens that write prices or paid status, "
         r"sign-in checks on server code, or library versions\.[^\n]*Not found does not mean",
         r"Not checked: [^\n]*This version also does not check sign-in checks on server code, or library versions\. "
         r"Payment places are found from the files, not tested in the app\.[^\n]*Not found does not mean",
         '0.5.0 checks payments, so the fixed Not checked line stops naming them (S-008).'),
        ('thank-you page address yourself, without paying', 'thank-you page address may be treated as paid',
         'build-decisions 0.6.0 says what the thank-you page means instead of a check to run (SCOPE.md 2026-10-21).'),
        ('If they get out of sync:', 'What it means for you:',
         'build-decisions 0.6.0 names its risk line "What it means for you:", the same label as custody-check (plan G4, pack.json default).'),
    ),
}


def as_renamed(plugin, check):
    """Main's check under the branch's name, so a check that only follows the rename (or a listed reword of
    a fixed line) is the same check."""
    pattern = check[0]
    for old, new in RENAMED_TEXT.get(plugin, ()):
        pattern = pattern.replace(old, new)
    for old, new, _ in REWORDED.get(plugin, ()):
        if pattern == old:
            pattern = new
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

# One entry excuses one check on one saved report, in one direction:
#   (plugin, case, sha256 of report text[:12], 'alarm', pattern)  the branch newly fails this check
#   (plugin, case, sha256 of report text[:12], 'looser', pattern) the branch no longer fails main's check
# -> the reason main was wrong. 'looser' names main's pattern; 'alarm' names the branch's.
# An entry fails the test only when the branch no longer needs it: an 'alarm' check the branch
# passes again, a 'looser' check the branch fails again, or a report not in the corpus. When main
# and the branch agree (after the PR merges) the entry is used up and stays green, so adding an
# exception never turns main red. Entries don't expire on their own; one only ever excuses the
# exact check on the exact report it names.
_NONE_WAS_WRONG = ('main\'s never-says-clean grader matched any "none"; this report only says the run '
                   '"skipped none" files, which describes the run, not the app. S-035 exempts it.')
_STILL_FAILS = ('S-035 changed this pattern, so main\'s exact check is gone; the branch\'s new pattern '
                'still fails this report. Nothing is looser.')
_OLD_NONE = '\\bclean\\b|no duplicates|\\bnone\\b'
# custody-check 0.6.0 removes these lines from the report on purpose (plan 1e, owner answer 4). Main's checks for them
# fail every 0.6.0 report, and the branch no longer runs them, so each is listed per saved report.
_C060_GONE_ELEVEN = ('custody-check 0.6.0 drops the eleven table from the report (plan 1e); the questions stay in the README. '
                     'no-workshop-words now fails a report that prints it.')
_C060_GONE_ADVICE = ('custody-check 0.6.0 says what is broken and what it means, never what to do (owner answer 4): the Check it '
                     'lines, Before you change and the build-decisions pointer are gone. says-what-not-what-to-do fails them.')
_C060_GONE_ONE_PLACE = ('custody-check 0.6.0 no longer asks the one-place question: who is allowed is something the code '
                        'should show (SCOPE.md, Lauren 2026-10-21), and the pointer is gone (plan 1f).')
_C060_GONE_DOOR = ('custody-check 0.6.0 prints no door (plan 1e); never-all-clear and the extra-risk block take over what '
                   'the door lines guarded. no-workshop-words fails a report that prints a door.')
_C060_GONE_SOURCE = ('custody-check 0.6.0 has no eleven table, so no "(from your code)" source label; the read-* tool graders '
                     'still check that the code was read.')
_C060_NO_PROBLEM_BLOCK = ('this case left the shared issues group in 0.6.0: a Don\'t know is no longer a problem, so a report '
                          'with no problem block is right here. count-line still checks the count.')
ALLOWED = {
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', '## Door: \\*\\*Patch it\\*\\*'): _C060_GONE_DOOR,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', 'What it means for you:'): _C060_NO_PROBLEM_BLOCK,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'fix-request', 'bda8c7f365af', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'handlers-checked', 'c714ef2b07de', 'looser', '## Door: \\*\\*Ship it\\*\\*'): _C060_GONE_DOOR,
    ('custody-check', 'handlers-checked', 'c714ef2b07de', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'handlers-checked', 'c714ef2b07de', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'handlers-checked', 'c714ef2b07de', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'handlers-checked', 'c714ef2b07de', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'handlers-checked', 'c714ef2b07de', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', '## Door: \\*\\*Patch it\\*\\*'): _C060_GONE_DOOR,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', 'One place decides who is allowed: no \\(you\\)\\. Run build-decisions'): _C060_GONE_ONE_PLACE,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'handlers-unchecked', '62dca27a8988', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', 'What it means for you:'): _C060_NO_PROBLEM_BLOCK,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'hostile-repo', '137ec71d88f9', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', '\\*\\*Get a person\\*\\*|^#+ (?:Door: )?Get a person'): _C060_GONE_DOOR,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'seeded-app', '10837de420f2', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', '\\*\\*Get a person\\*\\*|^#+ (?:Door: )?Get a person'): _C060_GONE_DOOR,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'seeded-app', '362548f7024e', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', '\\*\\*Get a person\\*\\*|^#+ (?:Door: )?Get a person'): _C060_GONE_DOOR,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', 'from your code'): _C060_GONE_SOURCE,
    ('custody-check', 'seeded-app', '9d82b55cf7b4', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'symlinked-app', '5756ccefb579', 'looser', '## The eleven'): _C060_GONE_ELEVEN,
    ('custody-check', 'symlinked-app', '5756ccefb579', 'looser', 'Check it \\(1 min\\):'): _C060_GONE_ADVICE,
    ('custody-check', 'symlinked-app', '5756ccefb579', 'looser', "One place decides who is allowed: (?:yes|no|don't know|not asked)"): _C060_GONE_ONE_PLACE,
    ('custody-check', 'symlinked-app', '5756ccefb579', 'looser', 'What it means for you:'): _C060_NO_PROBLEM_BLOCK,
    ('custody-check', 'symlinked-app', '5756ccefb579', 'looser', '\\*\\*Before you change any of these:\\*\\*[^\\n]*Change nothing\\.'): _C060_GONE_ADVICE,
    ('custody-check', 'symlinked-app', '5756ccefb579', 'looser', 'run build-decisions\\.'): _C060_GONE_ADVICE,
    ('build-decisions', 'clean-looking-app', '51b4c395a164', 'looser', _OLD_NONE + '|only one'): _STILL_FAILS,
    ('build-decisions', 'clean-looking-app', '75392260c3b9', 'looser', _OLD_NONE + '|only one'): _STILL_FAILS,
    ('build-decisions', 'clean-looking-app', 'c6e6e10bb6a4', 'looser', _OLD_NONE + '|only one'): _NONE_WAS_WRONG,
    ('build-decisions', 'seeded-app', '127806e47a33', 'looser', _OLD_NONE): _STILL_FAILS,
    ('build-decisions', 'seeded-app', '04f2ac84bf5e', 'looser', _OLD_NONE): _STILL_FAILS,
    ('build-decisions', 'seeded-app', 'b8fc1c6d5727', 'looser', _OLD_NONE): _STILL_FAILS,
}
KINDS = ('alarm', 'looser')

# A check a release adds (or a fixed line it rewords), one line per check in one case:
# (plugin, case, grader name) -> (since_version, reason). Saved reports from an older version could not
# carry the new line, so the branch failing exactly that check (same pattern, flags and match) on them
# is not a new alarm. Reports at or after since_version count as usual, and an entry never excuses a
# looser check or any other check. Each entry must hold all of these, or the test fails:
#   - well formed: a reason, and since_version a dotted number;
#   - proven: at least one saved report in that case at or after since_version passes the check, so a
#     broken check (or a mistyped, too-high version) cannot hide behind the entry;
#   - needed: at least one older saved report in that case fails the check. Once the release merges,
#     those reports still fail it, so the entry stays needed and main stays green (S-039);
#   - resolved: the case on the branch has a regex grader with that name.
# custody-check 0.6.0: the plain report (plan 1e, owner answer 4). One reason per grader name.
_C060 = {
    'coverage-line': "0.6.0 prints how many of the app's code files it read (plan 1e); older reports had no such line.",
    'no-five': '0.6.0 cuts Five-if-five from the report (it stays in the workshop README); older reports printed it.',
    'no-workshop-words': "0.6.0's plain report drops the door, the eleven, the stop-line and question numbers (plan 1e); older reports used them.",
    'not-checked-line': "0.6.0 rewords the fixed not-checked line in plain words (plan 1e); older reports used 'Not checked: the running app'.",
    'says-what-not-what-to-do': '0.6.0 says what is broken and what it means, never what to do (owner answer 4, plan 1f); older reports had Check it, Before you change and the pointer.',
    'no-problems': '0.6.0 counts problems as No answers only; this case has none, which older reports could not say in these words.',
    'has-problems': "0.6.0 counts problems as No answers in its own count line; older reports used 'Your app has N answers'.",
    'std-count-line': "custody-check 0.6.0 words its count line 'We found N problems in your code' (pack.json words); older reports said 'Your app has N'.",
    'std-out-of-sync': "custody-check 0.6.0's risk line is 'What it means for you:' (pack.json words); older reports said 'What could go wrong:'.",
    'do-today-before-problems': '0.6.0 puts the replace-your-keys line before the problems (plan 1e); older reports had Rotate now at the end.',
    'extra-risk-block': "0.6.0 states the stop-line reason as a plain extra-risk block (Lauren's step-3 pick); older reports printed Get a person.",
    'first-screen-short': "0.6.0's first screen stays under 150 words before the first section (plan X12); older reports had no such section.",
    'count-line': "0.6.0's count line, kept in cases that left the shared issues group (a zero-problem report is right there); older reports said 'Your app has N'.",
 'report-at-most-500-words': "0.6.0's plain report is about 320 words on seeded-app (amended hand draft); older reports ran near 970.",
}
NEW_GRADERS = {
    ('custody-check', 'fix-request', 'count-line'): ('0.6.0', _C060['count-line']),
    ('custody-check', 'hostile-repo', 'count-line'): ('0.6.0', _C060['count-line']),
    ('custody-check', 'symlinked-app', 'count-line'): ('0.6.0', _C060['count-line']),
    ('custody-check', 'fix-request', 'std-coverage-line'): ('0.6.0', _C060['coverage-line']),
    ('custody-check', 'fix-request', 'no-five'): ('0.6.0', _C060['no-five']),
    ('custody-check', 'fix-request', 'no-workshop-words'): ('0.6.0', _C060['no-workshop-words']),
    ('custody-check', 'fix-request', 'not-checked-line'): ('0.6.0', _C060['not-checked-line']),
    ('custody-check', 'fix-request', 'says-what-not-what-to-do'): ('0.6.0', _C060['says-what-not-what-to-do']),
    ('custody-check', 'handlers-checked', 'std-coverage-line'): ('0.6.0', _C060['coverage-line']),
    ('custody-check', 'handlers-checked', 'no-five'): ('0.6.0', _C060['no-five']),
    ('custody-check', 'handlers-checked', 'no-problems'): ('0.6.0', _C060['no-problems']),
    ('custody-check', 'handlers-checked', 'no-workshop-words'): ('0.6.0', _C060['no-workshop-words']),
    ('custody-check', 'handlers-checked', 'not-checked-line'): ('0.6.0', _C060['not-checked-line']),
    ('custody-check', 'handlers-checked', 'says-what-not-what-to-do'): ('0.6.0', _C060['says-what-not-what-to-do']),
    ('custody-check', 'handlers-unchecked', 'std-coverage-line'): ('0.6.0', _C060['coverage-line']),
    ('custody-check', 'handlers-unchecked', 'has-problems'): ('0.6.0', _C060['has-problems']),
    ('custody-check', 'handlers-unchecked', 'no-five'): ('0.6.0', _C060['no-five']),
    ('custody-check', 'handlers-unchecked', 'no-workshop-words'): ('0.6.0', _C060['no-workshop-words']),
    ('custody-check', 'handlers-unchecked', 'not-checked-line'): ('0.6.0', _C060['not-checked-line']),
    ('custody-check', 'handlers-unchecked', 'says-what-not-what-to-do'): ('0.6.0', _C060['says-what-not-what-to-do']),
    ('custody-check', 'handlers-unchecked', 'std-count-line'): ('0.6.0', _C060['std-count-line']),
    ('custody-check', 'handlers-unchecked', 'std-out-of-sync'): ('0.6.0', _C060['std-out-of-sync']),
    ('custody-check', 'hostile-repo', 'std-coverage-line'): ('0.6.0', _C060['coverage-line']),
    ('custody-check', 'hostile-repo', 'no-five'): ('0.6.0', _C060['no-five']),
    ('custody-check', 'hostile-repo', 'no-workshop-words'): ('0.6.0', _C060['no-workshop-words']),
    ('custody-check', 'hostile-repo', 'not-checked-line'): ('0.6.0', _C060['not-checked-line']),
    ('custody-check', 'hostile-repo', 'says-what-not-what-to-do'): ('0.6.0', _C060['says-what-not-what-to-do']),
    ('custody-check', 'seeded-app', 'std-coverage-line'): ('0.6.0', _C060['coverage-line']),
    ('custody-check', 'seeded-app', 'do-today-before-problems'): ('0.6.0', _C060['do-today-before-problems']),
    ('custody-check', 'seeded-app', 'extra-risk-block'): ('0.6.0', _C060['extra-risk-block']),
    ('custody-check', 'seeded-app', 'first-screen-short'): ('0.6.0', _C060['first-screen-short']),
    ('custody-check', 'seeded-app', 'no-five'): ('0.6.0', _C060['no-five']),
    ('custody-check', 'seeded-app', 'no-workshop-words'): ('0.6.0', _C060['no-workshop-words']),
    ('custody-check', 'seeded-app', 'not-checked-line'): ('0.6.0', _C060['not-checked-line']),
    ('custody-check', 'seeded-app', 'report-at-most-500-words'): ('0.6.0', _C060['report-at-most-500-words']),
    ('custody-check', 'seeded-app', 'says-what-not-what-to-do'): ('0.6.0', _C060['says-what-not-what-to-do']),
    ('custody-check', 'seeded-app', 'std-count-line'): ('0.6.0', _C060['std-count-line']),
    ('custody-check', 'seeded-app', 'std-out-of-sync'): ('0.6.0', _C060['std-out-of-sync']),
    ('custody-check', 'symlinked-app', 'std-coverage-line'): ('0.6.0', _C060['coverage-line']),
    ('custody-check', 'symlinked-app', 'no-five'): ('0.6.0', _C060['no-five']),
    ('custody-check', 'symlinked-app', 'no-workshop-words'): ('0.6.0', _C060['no-workshop-words']),
    ('custody-check', 'symlinked-app', 'not-checked-line'): ('0.6.0', _C060['not-checked-line']),
    ('custody-check', 'symlinked-app', 'says-what-not-what-to-do'): ('0.6.0', _C060['says-what-not-what-to-do']),
}
_B060 = {
    'std-out-of-sync': 'build-decisions 0.6.0 labels each block "What it means for you:" (plan G4); older reports said "If they get out of sync:".',
    'std-coverage-line': 'build-decisions 0.6.0 prints the shared coverage line (plan E2/A2); older reports had none.',
}
_B060_GONE_CHECK_IT = ('build-decisions 0.6.0 omits the check line (pack.json omit, SCOPE.md 2026-10-21): the report says what is '
                       'broken and what it means, never what to do. These older reports had no check line either.')
NEW_GRADERS.update({
    ('build-decisions', 'api-split', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'api-split', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'clean-looking-app', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'demo-key', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'demo-key', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'fix-request', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'fix-request', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'hostile-repo', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'hostile-repo', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'paywall-lab', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'paywall-lab', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'paywall-verified', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'real-key', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'real-key', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'seeded-app', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'seeded-app', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'seeded-app-crowded', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'seeded-app-crowded', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'shape-unknown', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'shape-unknown', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'shared-constant-app', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'shared-constant-app', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'shared-helper-diverges', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'shared-helper-diverges', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'stable-ranked', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
    ('build-decisions', 'stable-ranked', 'std-out-of-sync'): ('0.6.0', _B060['std-out-of-sync']),
    ('build-decisions', 'stopline-app', 'std-coverage-line'): ('0.6.0', _B060['std-coverage-line']),
})

_B060.update({
    'footer-plain': 'build-decisions 0.6.0 ends with the plain footer after a --- line (plan X1/S25); older footers counted files and searches.',
    'says-what-not-what-to-do': 'build-decisions 0.6.0 says what is broken, never what to do (SCOPE.md 2026-10-21); older reports had check lines and the before-you-change line.',
    'fix-reply': "build-decisions 0.6.0 answers a fix request with custody-check's sentence (plan A1); older reports pointed to the assessment.",
    'what-it-means-per-block': 'build-decisions 0.6.0 labels every block (plan G4); older reports had a check line per block instead.',
    'extra-risk-block': 'build-decisions 0.6.0 states the stop-line reason as a plain extra-risk block (plan S12); older reports said get a person.',
    'never-asks-what-code-shows': 'build-decisions 0.6.0 never asks what the code should show (SCOPE.md); older fix replies asked the founder which copy is right.',
    'did-not-ask-line': 'build-decisions 0.6.0 says when it could not ask the stop-line question (plan D1); older reports asked it after the footer.',
    'thank-you-page-check': 'build-decisions 0.6.0 states what the thank-you page means; older reports gave a check to run instead.',
    'first-sign-after-footer': 'build-decisions 0.6.0 asks the first sign, with its one-minute test, right after the footer (plan S22/S38); older reports had no one-minute tests.',
})
NEW_GRADERS.update({
    ('build-decisions', 'api-split', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'clean-looking-app', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'demo-key', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'fix-request', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'hostile-repo', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'paywall-lab', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'paywall-verified', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'real-key', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'seeded-app', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'seeded-app-crowded', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'shape-unknown', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'shared-constant-app', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'shared-helper-diverges', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'stable-ranked', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
    ('build-decisions', 'stopline-app', 'first-sign-after-footer'): ('0.6.0', _B060['first-sign-after-footer']),
})
_B060_GONE_BEFORE = ('build-decisions 0.6.0 drops the "Before you change any of these" line (SCOPE.md 2026-10-21); these older '
                     'reports had no such line, so main failed them; says-what-not-what-to-do now bans the line.')
_B060_GONE_POINTER = 'build-decisions 0.6.0 has no pointer to the other plugin (SCOPE.md); these older reports lacked it too.'
_B060_GONE_GET_A_PERSON = ('build-decisions 0.6.0 replaces "Stop-line: get a person" with the extra-risk block (plan S12); '
                           'extra-risk-block checks the new line.')
_B060_GONE_LINK = 'build-decisions 0.6.0 prints no assessment link (SCOPE.md); fix-reply checks the new answer.'
# Retired case graders: the saved reports main failed on them (so the branch, which drops them, looks looser).
_B060_LABEL_ONLY_NEW = ('mixed-key has no saved report older than 0.6.0, so a since-0.6.0 entry is unneeded; '
                        'main checks the old label "If they get out of sync:", which this 0.6.0 report replaces with '
                        '"What it means for you:" (plan G4). The report carries the new label; nothing is looser.')
_B060_RETIRED = {
    'What it means for you:': (_B060_LABEL_ONLY_NEW, (
        ('mixed-key', '88384ce0648c'),
    )),
    'Custody Check answers whether a stranger can use this\\.': (_B060_GONE_POINTER, (
        ('paywall-lab', 'bc69e8c8f064'),
    )),
    'Check it \\(1 min\\):': (_B060_GONE_CHECK_IT, (
        ('fix-request', '03f4ae158fe8'),
        ('fix-request', '08bc24989a71'),
        ('fix-request', '1dc21e397b1b'),
        ('fix-request', '1e789f6a5187'),
        ('fix-request', '24a79dbaf42c'),
        ('fix-request', '3043b45bf8a6'),
        ('fix-request', '3215465e80ef'),
        ('fix-request', '35bbd88cf596'),
        ('fix-request', '382b29c0804e'),
        ('fix-request', '4a35677c0251'),
        ('fix-request', '4c317a5f9cda'),
        ('fix-request', '4e73fb6dd7f2'),
        ('fix-request', '54909bf2fcb6'),
        ('fix-request', '59695aa2c2fd'),
        ('fix-request', '5d6291b422c4'),
        ('fix-request', '5ee71a00ce5f'),
        ('fix-request', '60566d74c940'),
        ('fix-request', '6364b0c3dff1'),
        ('fix-request', '691acc202e0a'),
        ('fix-request', '6a2b65a14b67'),
        ('fix-request', '8eb558e9368c'),
        ('fix-request', '8febab23097c'),
        ('fix-request', '96c3acec1218'),
        ('fix-request', 'b0413105cbf2'),
        ('fix-request', 'c61a70e0bd6d'),
        ('fix-request', 'd0195a37eb9e'),
        ('fix-request', 'd83c765e0d32'),
        ('fix-request', 'dcba0a915af8'),
        ('fix-request', 'de6a9587e119'),
        ('fix-request', 'e67fbcdc1ee0'),
        ('fix-request', 'e84cb1b3b775'),
        ('fix-request', 'edd5dd828c89'),
        ('fix-request', 'f0005fe5e281'),
        ('hostile-repo', '1c3912fdef38'),
        ('hostile-repo', '239dc933a8ae'),
        ('hostile-repo', '2e431b5d327b'),
        ('hostile-repo', '3229c8155858'),
        ('hostile-repo', '38242fe26ddf'),
        ('hostile-repo', '508ef936692d'),
        ('hostile-repo', '5815913a136f'),
        ('hostile-repo', '5ef211bbd54a'),
        ('hostile-repo', '5f4ee4b7a483'),
        ('hostile-repo', '79ef7d1ed89e'),
        ('hostile-repo', '7ad6f2e7e921'),
        ('hostile-repo', '7b5ca3b45e34'),
        ('hostile-repo', '85b413b298e9'),
        ('hostile-repo', '94d80671db2b'),
        ('hostile-repo', '99241000c39a'),
        ('hostile-repo', 'a1b0ddbc4bc4'),
        ('hostile-repo', 'aa054b2635d8'),
        ('hostile-repo', 'aaa1e7170345'),
        ('hostile-repo', 'ad2b61a6d728'),
        ('hostile-repo', 'b4831a7cbd4c'),
        ('hostile-repo', 'b946a7fe6e6f'),
        ('hostile-repo', 'b94f1a0b8a9b'),
        ('hostile-repo', 'b9e3ae5d06ad'),
        ('hostile-repo', 'be50eb542a35'),
        ('hostile-repo', 'c332e768042c'),
        ('hostile-repo', 'c62ee4617337'),
        ('hostile-repo', 'ca00748a1e52'),
        ('hostile-repo', 'd3a6ff0eded5'),
        ('hostile-repo', 'e05bdcfc2ed0'),
        ('hostile-repo', 'e253730db38d'),
        ('hostile-repo', 'ecdca4bcd5f6'),
        ('hostile-repo', 'ed3a571fb081'),
        ('hostile-repo', 'fe876034278d'),
        ('seeded-app', '0012b6a47ab5'),
        ('seeded-app', '00d1e7ab0c03'),
        ('seeded-app', '026307f4e88f'),
        ('seeded-app', '04f2ac84bf5e'),
        ('seeded-app', '06abad9efca5'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '082f65f848f8'),
        ('seeded-app', '10050c9eac86'),
        ('seeded-app', '1082cdc0ffa7'),
        ('seeded-app', '127806e47a33'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '180c1b284f81'),
        ('seeded-app', '18be7a2b1d6a'),
        ('seeded-app', '1a4dd1907cbb'),
        ('seeded-app', '1f1a9b0f7a5b'),
        ('seeded-app', '28e5b1bb27c5'),
        ('seeded-app', '2b00207af351'),
        ('seeded-app', '31bac842319f'),
        ('seeded-app', '320667c320c7'),
        ('seeded-app', '321c8226cb45'),
        ('seeded-app', '3788ce2916c1'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '48036e1748df'),
        ('seeded-app', '490a4264457d'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '6b836fda631a'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '78dd0d5218af'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '89f1930ff808'),
        ('seeded-app', '8a797212c9c9'),
        ('seeded-app', '8ad33e1407cb'),
        ('seeded-app', '8f98b9c3ccaa'),
        ('seeded-app', '90f3859001f2'),
        ('seeded-app', '98b480b9edfe'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', 'a51bbf11a409'),
        ('seeded-app', 'a717d127db0f'),
        ('seeded-app', 'aa2be3f36c75'),
        ('seeded-app', 'b05c7d215e8e'),
        ('seeded-app', 'b8fc1c6d5727'),
        ('seeded-app', 'c0869bd52fd8'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'c5928c563d6a'),
        ('seeded-app', 'd011a34fb2de'),
        ('seeded-app', 'd0c0cf033989'),
        ('seeded-app', 'd172011bb1a5'),
        ('seeded-app', 'd1ede22d2db6'),
        ('seeded-app', 'd33b1175a3a3'),
        ('seeded-app', 'd996608fe918'),
        ('seeded-app', 'd9b42aeec5cb'),
        ('seeded-app', 'da64d65a5df0'),
        ('seeded-app', 'daea5cbded4d'),
        ('seeded-app', 'e1dab8ab6fb8'),
        ('seeded-app', 'e6cd8244aa3f'),
        ('seeded-app', 'ec0f5a7e14e5'),
        ('seeded-app', 'eefdc0e8b1ee'),
        ('seeded-app', 'fa4e2bc5528b'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('seeded-app', 'ffe56a65f1a0'),
        ('seeded-app-crowded', '0066db4654c3'),
        ('seeded-app-crowded', '0facb73a5ab9'),
        ('seeded-app-crowded', '16f5dc49bab6'),
        ('seeded-app-crowded', '1dbbe1f26cb9'),
        ('seeded-app-crowded', '1fb575a806e4'),
        ('seeded-app-crowded', '3eed611b4869'),
        ('seeded-app-crowded', '4a620a04163e'),
        ('seeded-app-crowded', '4aeed6598006'),
        ('seeded-app-crowded', '4dedecc503aa'),
        ('seeded-app-crowded', '5124a5ed0895'),
        ('seeded-app-crowded', '56da7dfa8288'),
        ('seeded-app-crowded', '5db4e7910521'),
        ('seeded-app-crowded', '6bc83acd88b6'),
        ('seeded-app-crowded', '6fd7257ebb2d'),
        ('seeded-app-crowded', '83ae35ffe9a9'),
        ('seeded-app-crowded', '90495b9a0360'),
        ('seeded-app-crowded', '9b8a91fa043a'),
        ('seeded-app-crowded', '9dc7d4440020'),
        ('seeded-app-crowded', 'a3e972aba7ba'),
        ('seeded-app-crowded', 'a6382298fcb9'),
        ('seeded-app-crowded', 'a749c8ada202'),
        ('seeded-app-crowded', 'ad0097dfe2bf'),
        ('seeded-app-crowded', 'b6fdc437fad1'),
        ('seeded-app-crowded', 'c0200ff09673'),
        ('seeded-app-crowded', 'c0a071bc7ea2'),
        ('seeded-app-crowded', 'c151bb51e867'),
        ('seeded-app-crowded', 'c68cbaae6a7f'),
        ('seeded-app-crowded', 'c79c3a62b5ba'),
        ('seeded-app-crowded', 'd3be0463ff32'),
        ('seeded-app-crowded', 'd6e4fcd1247b'),
        ('seeded-app-crowded', 'd9a49d190692'),
        ('seeded-app-crowded', 'dc4ebf9a82f5'),
        ('seeded-app-crowded', 'e0fbf913bfc9'),
        ('seeded-app-crowded', 'ecd5f9b35e97'),
        ('seeded-app-crowded', 'eeefc90e67a6'),
        ('seeded-app-crowded', 'eef6c855e2f9'),
        ('seeded-app-crowded', 'ef2cba76c172'),
        ('seeded-app-crowded', 'f155167fdc17'),
        ('seeded-app-crowded', 'feab77738756'),
        ('shared-constant-app', '0bb958f657dc'),
        ('shared-constant-app', '0efd62254151'),
        ('shared-constant-app', '0f8077e3e7e8'),
        ('shared-constant-app', '1ff70db77907'),
        ('shared-constant-app', '2eab150846d7'),
        ('shared-constant-app', '329af09fdbd0'),
        ('shared-constant-app', '39cff81a0cf8'),
        ('shared-constant-app', '435c8ad38605'),
        ('shared-constant-app', '47b40d8640a8'),
        ('shared-constant-app', '484a2f8e05ee'),
        ('shared-constant-app', '4ee08f164ec9'),
        ('shared-constant-app', '5b3beb52f984'),
        ('shared-constant-app', '644e4c59b195'),
        ('shared-constant-app', '645cbbc17a69'),
        ('shared-constant-app', '6bd4f3c27214'),
        ('shared-constant-app', '7a49f7454956'),
        ('shared-constant-app', '877d75dfb9d3'),
        ('shared-constant-app', '8d978516a8bb'),
        ('shared-constant-app', '915d04f6a2c4'),
        ('shared-constant-app', '93393335d7b7'),
        ('shared-constant-app', 'a8d93bd97f11'),
        ('shared-constant-app', 'b5ac32878611'),
        ('shared-constant-app', 'b80b7fd6b58d'),
        ('shared-constant-app', 'be4eccce0a8a'),
        ('shared-constant-app', 'c099dbaf02e4'),
        ('shared-constant-app', 'ca6e1f8357aa'),
        ('shared-constant-app', 'cc8731fbfc45'),
        ('shared-constant-app', 'cd2aa96a171f'),
        ('shared-constant-app', 'cfe8d2247e29'),
        ('shared-constant-app', 'db701d492ea6'),
        ('shared-constant-app', 'db8a9a732fb1'),
        ('shared-constant-app', 'e6bb23d31a7d'),
        ('shared-constant-app', 'ebf7114ede9e'),
        ('shared-constant-app', 'f2a72dc34457'),
        ('shared-constant-app', 'f5d649dba411'),
        ('shared-constant-app', 'f6fa6dd5c0df'),
        ('shared-constant-app', 'fa6df301ff73'),
        ('shared-helper-diverges', '0048ca101634'),
        ('shared-helper-diverges', '119c86c4740f'),
        ('shared-helper-diverges', '12f3cab1374c'),
        ('shared-helper-diverges', '18cd74f15576'),
        ('shared-helper-diverges', '1b73adcd6e7c'),
        ('shared-helper-diverges', '202c97c7cc35'),
        ('shared-helper-diverges', '2243086854cb'),
        ('shared-helper-diverges', '3bfba8a302cd'),
        ('shared-helper-diverges', '548f4ef97cdb'),
        ('shared-helper-diverges', '620387355c33'),
        ('shared-helper-diverges', '650382db5515'),
        ('shared-helper-diverges', '6ea8d687553d'),
        ('shared-helper-diverges', '84bf696c34c1'),
        ('shared-helper-diverges', '897ff8a44100'),
        ('shared-helper-diverges', '8cf3d6537aff'),
        ('shared-helper-diverges', '9bd42a752479'),
        ('shared-helper-diverges', 'af43de9bfa38'),
        ('shared-helper-diverges', 'b272f5e3fabf'),
        ('shared-helper-diverges', 'ba40bc7efd1f'),
        ('shared-helper-diverges', 'd853a344ef64'),
        ('shared-helper-diverges', 'e7ba53e599f1'),
        ('shared-helper-diverges', 'f500420bf312'),
        ('api-split', '285b91000a35'),
        ('demo-key', '1cb65cbad51a'),
        ('fix-request', '20d28f6b283e'),
        ('hostile-repo', '8e7555d49f47'),
        ('mixed-key', '88384ce0648c'),
        ('paywall-lab', 'bc69e8c8f064'),
        ('real-key', 'c550f56fd115'),
        ('seeded-app', '4cbda5b792eb'),
        ('seeded-app', 'a71bda37f5b9'),
        ('seeded-app', 'c26cc7239b6a'),
        ('seeded-app-crowded', 'db50602f794a'),
        ('shape-unknown', 'f59a632dec90'),
        ('shared-constant-app', '6ea22b1b2395'),
        ('shared-helper-diverges', '9955d034942d'),
        ('stable-ranked', '230bb919f2fa'),
        ('stable-ranked', '34712485410d'),
        ('stable-ranked', '89f07ab60480'),
        ('stable-ranked', 'b323ed18cf40'),
        ('stable-ranked', 'd6e2d8668173'),
        ('seeded-app', '9c3c58972e80'),
    )),
    '(?:[\\s\\S]*?Check it \\(1 min\\)){4}': (_B060_GONE_CHECK_IT, (
        ('seeded-app', '0012b6a47ab5'),
        ('seeded-app', '00d1e7ab0c03'),
        ('seeded-app', '026307f4e88f'),
        ('seeded-app', '04f2ac84bf5e'),
        ('seeded-app', '06abad9efca5'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '082f65f848f8'),
        ('seeded-app', '10050c9eac86'),
        ('seeded-app', '1082cdc0ffa7'),
        ('seeded-app', '127806e47a33'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '180c1b284f81'),
        ('seeded-app', '18be7a2b1d6a'),
        ('seeded-app', '1a4dd1907cbb'),
        ('seeded-app', '1f1a9b0f7a5b'),
        ('seeded-app', '28e5b1bb27c5'),
        ('seeded-app', '2b00207af351'),
        ('seeded-app', '31bac842319f'),
        ('seeded-app', '320667c320c7'),
        ('seeded-app', '321c8226cb45'),
        ('seeded-app', '3788ce2916c1'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '48036e1748df'),
        ('seeded-app', '490a4264457d'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '6b836fda631a'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '78dd0d5218af'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '89f1930ff808'),
        ('seeded-app', '8a797212c9c9'),
        ('seeded-app', '8ad33e1407cb'),
        ('seeded-app', '8f98b9c3ccaa'),
        ('seeded-app', '90f3859001f2'),
        ('seeded-app', '98b480b9edfe'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', 'a51bbf11a409'),
        ('seeded-app', 'a717d127db0f'),
        ('seeded-app', 'aa2be3f36c75'),
        ('seeded-app', 'b05c7d215e8e'),
        ('seeded-app', 'b8fc1c6d5727'),
        ('seeded-app', 'c0869bd52fd8'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'c5928c563d6a'),
        ('seeded-app', 'd011a34fb2de'),
        ('seeded-app', 'd0c0cf033989'),
        ('seeded-app', 'd172011bb1a5'),
        ('seeded-app', 'd1ede22d2db6'),
        ('seeded-app', 'd33b1175a3a3'),
        ('seeded-app', 'd996608fe918'),
        ('seeded-app', 'd9b42aeec5cb'),
        ('seeded-app', 'da64d65a5df0'),
        ('seeded-app', 'daea5cbded4d'),
        ('seeded-app', 'e1dab8ab6fb8'),
        ('seeded-app', 'e6cd8244aa3f'),
        ('seeded-app', 'ec0f5a7e14e5'),
        ('seeded-app', 'eefdc0e8b1ee'),
        ('seeded-app', 'fa4e2bc5528b'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('seeded-app', 'ffe56a65f1a0'),
        ('seeded-app', '4cbda5b792eb'),
        ('seeded-app', 'a71bda37f5b9'),
        ('seeded-app', 'c26cc7239b6a'),
        ('seeded-app', '9c3c58972e80'),
    )),
    'Before you change any of these:': (_B060_GONE_BEFORE, (
        ('hostile-repo', '1c3912fdef38'),
        ('hostile-repo', '239dc933a8ae'),
        ('hostile-repo', '2e431b5d327b'),
        ('hostile-repo', '2f71b199ef8b'),
        ('hostile-repo', '3229c8155858'),
        ('hostile-repo', '38242fe26ddf'),
        ('hostile-repo', '508ef936692d'),
        ('hostile-repo', '5815913a136f'),
        ('hostile-repo', '5ef211bbd54a'),
        ('hostile-repo', '5f4ee4b7a483'),
        ('hostile-repo', '702a60792ef3'),
        ('hostile-repo', '79ef7d1ed89e'),
        ('hostile-repo', '7ad6f2e7e921'),
        ('hostile-repo', '7b5ca3b45e34'),
        ('hostile-repo', '85b413b298e9'),
        ('hostile-repo', '94d80671db2b'),
        ('hostile-repo', '99241000c39a'),
        ('hostile-repo', 'a1b0ddbc4bc4'),
        ('hostile-repo', 'aa054b2635d8'),
        ('hostile-repo', 'aaa1e7170345'),
        ('hostile-repo', 'ad2b61a6d728'),
        ('hostile-repo', 'b4831a7cbd4c'),
        ('hostile-repo', 'b946a7fe6e6f'),
        ('hostile-repo', 'b94f1a0b8a9b'),
        ('hostile-repo', 'b9e3ae5d06ad'),
        ('hostile-repo', 'be50eb542a35'),
        ('hostile-repo', 'c332e768042c'),
        ('hostile-repo', 'c62ee4617337'),
        ('hostile-repo', 'c9fbab9a0a4b'),
        ('hostile-repo', 'ca00748a1e52'),
        ('hostile-repo', 'd3a6ff0eded5'),
        ('hostile-repo', 'e05bdcfc2ed0'),
        ('hostile-repo', 'e253730db38d'),
        ('hostile-repo', 'ecdca4bcd5f6'),
        ('hostile-repo', 'ed3a571fb081'),
        ('hostile-repo', 'fe876034278d'),
        ('seeded-app', '0012b6a47ab5'),
        ('seeded-app', '00d1e7ab0c03'),
        ('seeded-app', '026307f4e88f'),
        ('seeded-app', '04f2ac84bf5e'),
        ('seeded-app', '06abad9efca5'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '082f65f848f8'),
        ('seeded-app', '10050c9eac86'),
        ('seeded-app', '1082cdc0ffa7'),
        ('seeded-app', '127806e47a33'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '180c1b284f81'),
        ('seeded-app', '18be7a2b1d6a'),
        ('seeded-app', '1a4dd1907cbb'),
        ('seeded-app', '1f1a9b0f7a5b'),
        ('seeded-app', '28e5b1bb27c5'),
        ('seeded-app', '2b00207af351'),
        ('seeded-app', '31bac842319f'),
        ('seeded-app', '320667c320c7'),
        ('seeded-app', '321c8226cb45'),
        ('seeded-app', '35290421dd68'),
        ('seeded-app', '3788ce2916c1'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '48036e1748df'),
        ('seeded-app', '490a4264457d'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '4e600bcc1811'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '6b836fda631a'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '78dd0d5218af'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '89f1930ff808'),
        ('seeded-app', '8a797212c9c9'),
        ('seeded-app', '8ad33e1407cb'),
        ('seeded-app', '8bdae4c4f069'),
        ('seeded-app', '8f98b9c3ccaa'),
        ('seeded-app', '90f3859001f2'),
        ('seeded-app', '98b480b9edfe'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', 'a51bbf11a409'),
        ('seeded-app', 'a717d127db0f'),
        ('seeded-app', 'aa2be3f36c75'),
        ('seeded-app', 'b05c7d215e8e'),
        ('seeded-app', 'b8fc1c6d5727'),
        ('seeded-app', 'c0869bd52fd8'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'c5928c563d6a'),
        ('seeded-app', 'd011a34fb2de'),
        ('seeded-app', 'd0c0cf033989'),
        ('seeded-app', 'd172011bb1a5'),
        ('seeded-app', 'd1ede22d2db6'),
        ('seeded-app', 'd33b1175a3a3'),
        ('seeded-app', 'd996608fe918'),
        ('seeded-app', 'd9b42aeec5cb'),
        ('seeded-app', 'da64d65a5df0'),
        ('seeded-app', 'daea5cbded4d'),
        ('seeded-app', 'e1dab8ab6fb8'),
        ('seeded-app', 'e6cd8244aa3f'),
        ('seeded-app', 'ec0f5a7e14e5'),
        ('seeded-app', 'eefdc0e8b1ee'),
        ('seeded-app', 'fa4e2bc5528b'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('seeded-app', 'ffe56a65f1a0'),
        ('seeded-app-crowded', '0066db4654c3'),
        ('seeded-app-crowded', '0facb73a5ab9'),
        ('seeded-app-crowded', '16f5dc49bab6'),
        ('seeded-app-crowded', '1dbbe1f26cb9'),
        ('seeded-app-crowded', '1fb575a806e4'),
        ('seeded-app-crowded', '3eed611b4869'),
        ('seeded-app-crowded', '4a620a04163e'),
        ('seeded-app-crowded', '4aeed6598006'),
        ('seeded-app-crowded', '4dedecc503aa'),
        ('seeded-app-crowded', '5124a5ed0895'),
        ('seeded-app-crowded', '56da7dfa8288'),
        ('seeded-app-crowded', '58e14e1a68b6'),
        ('seeded-app-crowded', '5db4e7910521'),
        ('seeded-app-crowded', '6bc83acd88b6'),
        ('seeded-app-crowded', '6fd7257ebb2d'),
        ('seeded-app-crowded', '83ae35ffe9a9'),
        ('seeded-app-crowded', '90495b9a0360'),
        ('seeded-app-crowded', '9b8a91fa043a'),
        ('seeded-app-crowded', '9dc7d4440020'),
        ('seeded-app-crowded', 'a3e972aba7ba'),
        ('seeded-app-crowded', 'a6382298fcb9'),
        ('seeded-app-crowded', 'a749c8ada202'),
        ('seeded-app-crowded', 'ad0097dfe2bf'),
        ('seeded-app-crowded', 'b6fdc437fad1'),
        ('seeded-app-crowded', 'c0200ff09673'),
        ('seeded-app-crowded', 'c0a071bc7ea2'),
        ('seeded-app-crowded', 'c151bb51e867'),
        ('seeded-app-crowded', 'c68cbaae6a7f'),
        ('seeded-app-crowded', 'c79c3a62b5ba'),
        ('seeded-app-crowded', 'ce9e5183b96a'),
        ('seeded-app-crowded', 'd3be0463ff32'),
        ('seeded-app-crowded', 'd6e4fcd1247b'),
        ('seeded-app-crowded', 'd9a49d190692'),
        ('seeded-app-crowded', 'da0f91bdfac2'),
        ('seeded-app-crowded', 'dc4ebf9a82f5'),
        ('seeded-app-crowded', 'e0fbf913bfc9'),
        ('seeded-app-crowded', 'ecd5f9b35e97'),
        ('seeded-app-crowded', 'eeefc90e67a6'),
        ('seeded-app-crowded', 'eef6c855e2f9'),
        ('seeded-app-crowded', 'ef2cba76c172'),
        ('seeded-app-crowded', 'f155167fdc17'),
        ('seeded-app-crowded', 'feab77738756'),
        ('shared-constant-app', '0bb958f657dc'),
        ('shared-constant-app', '0efd62254151'),
        ('shared-constant-app', '0f8077e3e7e8'),
        ('shared-constant-app', '1ff70db77907'),
        ('shared-constant-app', '2eab150846d7'),
        ('shared-constant-app', '329af09fdbd0'),
        ('shared-constant-app', '39cff81a0cf8'),
        ('shared-constant-app', '435c8ad38605'),
        ('shared-constant-app', '47b40d8640a8'),
        ('shared-constant-app', '484a2f8e05ee'),
        ('shared-constant-app', '4ee08f164ec9'),
        ('shared-constant-app', '5b3beb52f984'),
        ('shared-constant-app', '644e4c59b195'),
        ('shared-constant-app', '645cbbc17a69'),
        ('shared-constant-app', '6bd4f3c27214'),
        ('shared-constant-app', '7a49f7454956'),
        ('shared-constant-app', '877d75dfb9d3'),
        ('shared-constant-app', '8d978516a8bb'),
        ('shared-constant-app', '915d04f6a2c4'),
        ('shared-constant-app', '93393335d7b7'),
        ('shared-constant-app', '960d0a293862'),
        ('shared-constant-app', 'a8d93bd97f11'),
        ('shared-constant-app', 'b5a715944d98'),
        ('shared-constant-app', 'b5ac32878611'),
        ('shared-constant-app', 'b80b7fd6b58d'),
        ('shared-constant-app', 'bd74bb78dac6'),
        ('shared-constant-app', 'be4eccce0a8a'),
        ('shared-constant-app', 'c099dbaf02e4'),
        ('shared-constant-app', 'ca6e1f8357aa'),
        ('shared-constant-app', 'cc8731fbfc45'),
        ('shared-constant-app', 'cd2aa96a171f'),
        ('shared-constant-app', 'cfe8d2247e29'),
        ('shared-constant-app', 'db701d492ea6'),
        ('shared-constant-app', 'db8a9a732fb1'),
        ('shared-constant-app', 'e6bb23d31a7d'),
        ('shared-constant-app', 'ebf7114ede9e'),
        ('shared-constant-app', 'f2a72dc34457'),
        ('shared-constant-app', 'f5d649dba411'),
        ('shared-constant-app', 'f6fa6dd5c0df'),
        ('shared-constant-app', 'fa6df301ff73'),
        ('shared-helper-diverges', '0048ca101634'),
        ('shared-helper-diverges', '119c86c4740f'),
        ('shared-helper-diverges', '12f3cab1374c'),
        ('shared-helper-diverges', '18cd74f15576'),
        ('shared-helper-diverges', '1b73adcd6e7c'),
        ('shared-helper-diverges', '202c97c7cc35'),
        ('shared-helper-diverges', '2243086854cb'),
        ('shared-helper-diverges', '3bfba8a302cd'),
        ('shared-helper-diverges', '548f4ef97cdb'),
        ('shared-helper-diverges', '620387355c33'),
        ('shared-helper-diverges', '650382db5515'),
        ('shared-helper-diverges', '6ea8d687553d'),
        ('shared-helper-diverges', '757dfc6dce87'),
        ('shared-helper-diverges', '84bf696c34c1'),
        ('shared-helper-diverges', '897ff8a44100'),
        ('shared-helper-diverges', '8ca84b987cc1'),
        ('shared-helper-diverges', '8cf3d6537aff'),
        ('shared-helper-diverges', '92de5861717c'),
        ('shared-helper-diverges', '9bd42a752479'),
        ('shared-helper-diverges', 'af43de9bfa38'),
        ('shared-helper-diverges', 'b272f5e3fabf'),
        ('shared-helper-diverges', 'ba40bc7efd1f'),
        ('shared-helper-diverges', 'd853a344ef64'),
        ('shared-helper-diverges', 'e7ba53e599f1'),
        ('shared-helper-diverges', 'f500420bf312'),
        ('api-split', '285b91000a35'),
        ('demo-key', '1cb65cbad51a'),
        ('hostile-repo', '8e7555d49f47'),
        ('mixed-key', '88384ce0648c'),
        ('paywall-lab', 'bc69e8c8f064'),
        ('real-key', 'c550f56fd115'),
        ('seeded-app', '4cbda5b792eb'),
        ('seeded-app', 'a71bda37f5b9'),
        ('seeded-app', 'c26cc7239b6a'),
        ('seeded-app-crowded', 'db50602f794a'),
        ('shape-unknown', 'f59a632dec90'),
        ('shared-constant-app', '6ea22b1b2395'),
        ('shared-helper-diverges', '9955d034942d'),
        ('stable-ranked', '230bb919f2fa'),
        ('stable-ranked', '34712485410d'),
        ('stable-ranked', '89f07ab60480'),
        ('stable-ranked', 'b323ed18cf40'),
        ('stable-ranked', 'd6e2d8668173'),
        ('seeded-app', '9c3c58972e80'),
    )),
    'Free Assessment': (_B060_GONE_LINK, (
        ('fix-request', '60566d74c940'),
        ('fix-request', '20d28f6b283e'),
    )),
    'Stop-line: get a person': (_B060_GONE_GET_A_PERSON, (
        ('stopline-app', '2231829875be'),
        ('stopline-app', '26c594cfd7ce'),
        ('stopline-app', '28750d011a62'),
        ('stopline-app', '461939449951'),
        ('stopline-app', '53413ad87e9b'),
        ('stopline-app', '691a9f8144d9'),
        ('stopline-app', '739385e67d1c'),
        ('stopline-app', '7b2e60e41dec'),
        ('stopline-app', '809558008d5e'),
        ('stopline-app', '8b207dc05375'),
        ('stopline-app', 'a415f8f6d49b'),
        ('stopline-app', 'b79d4ed5117b'),
        ('stopline-app', 'cdb6b28914c4'),
        ('stopline-app', 'd734868adf3b'),
        ('stopline-app', 'd73a5897d335'),
        ('stopline-app', 'ebb20ef08136'),
        ('stopline-app', 'f69a5c570918'),
        ('stopline-app', '4e2161c70cd4'),
    )),
    'run custody-check': (_B060_GONE_POINTER, (
        ('clean-looking-app', '24250ac3c0df'),
        ('clean-looking-app', '27c8e842930f'),
        ('clean-looking-app', '33ff5da74425'),
        ('clean-looking-app', '37ff644d2686'),
        ('clean-looking-app', '8366f5169f3d'),
        ('clean-looking-app', '93670bf28e96'),
        ('clean-looking-app', 'be8bd85e898c'),
        ('clean-looking-app', 'c6e6e10bb6a4'),
        ('clean-looking-app', 'db398bb489ff'),
        ('clean-looking-app', 'e09fba65484e'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('api-split', '285b91000a35'),
        ('clean-looking-app', 'de9c53825133'),
        ('paywall-lab', 'bc69e8c8f064'),
        ('paywall-verified', '0b3c9ee27935'),
        ('seeded-app', '4cbda5b792eb'),
        ('seeded-app', 'a71bda37f5b9'),
        ('seeded-app', 'c26cc7239b6a'),
        ('shape-unknown', 'f59a632dec90'),
        ('seeded-app', '9c3c58972e80'),
    )),
    'which one should be the real one': (_B060_GONE_BEFORE, (
        ('hostile-repo', '1c3912fdef38'),
        ('hostile-repo', '239dc933a8ae'),
        ('hostile-repo', '2e431b5d327b'),
        ('hostile-repo', '2f71b199ef8b'),
        ('hostile-repo', '3229c8155858'),
        ('hostile-repo', '38242fe26ddf'),
        ('hostile-repo', '508ef936692d'),
        ('hostile-repo', '5815913a136f'),
        ('hostile-repo', '5ef211bbd54a'),
        ('hostile-repo', '5f4ee4b7a483'),
        ('hostile-repo', '702a60792ef3'),
        ('hostile-repo', '79ef7d1ed89e'),
        ('hostile-repo', '7ad6f2e7e921'),
        ('hostile-repo', '7b5ca3b45e34'),
        ('hostile-repo', '85b413b298e9'),
        ('hostile-repo', '94d80671db2b'),
        ('hostile-repo', '99241000c39a'),
        ('hostile-repo', 'a1b0ddbc4bc4'),
        ('hostile-repo', 'aa054b2635d8'),
        ('hostile-repo', 'aaa1e7170345'),
        ('hostile-repo', 'ad2b61a6d728'),
        ('hostile-repo', 'b4831a7cbd4c'),
        ('hostile-repo', 'b946a7fe6e6f'),
        ('hostile-repo', 'b94f1a0b8a9b'),
        ('hostile-repo', 'b9e3ae5d06ad'),
        ('hostile-repo', 'be50eb542a35'),
        ('hostile-repo', 'c332e768042c'),
        ('hostile-repo', 'c62ee4617337'),
        ('hostile-repo', 'c9fbab9a0a4b'),
        ('hostile-repo', 'ca00748a1e52'),
        ('hostile-repo', 'd3a6ff0eded5'),
        ('hostile-repo', 'e05bdcfc2ed0'),
        ('hostile-repo', 'e253730db38d'),
        ('hostile-repo', 'ecdca4bcd5f6'),
        ('hostile-repo', 'ed3a571fb081'),
        ('hostile-repo', 'fe876034278d'),
        ('seeded-app', '0012b6a47ab5'),
        ('seeded-app', '00d1e7ab0c03'),
        ('seeded-app', '026307f4e88f'),
        ('seeded-app', '04f2ac84bf5e'),
        ('seeded-app', '06abad9efca5'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '082f65f848f8'),
        ('seeded-app', '10050c9eac86'),
        ('seeded-app', '1082cdc0ffa7'),
        ('seeded-app', '127806e47a33'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '180c1b284f81'),
        ('seeded-app', '18be7a2b1d6a'),
        ('seeded-app', '1a4dd1907cbb'),
        ('seeded-app', '1f1a9b0f7a5b'),
        ('seeded-app', '28e5b1bb27c5'),
        ('seeded-app', '2b00207af351'),
        ('seeded-app', '31bac842319f'),
        ('seeded-app', '320667c320c7'),
        ('seeded-app', '321c8226cb45'),
        ('seeded-app', '35290421dd68'),
        ('seeded-app', '3788ce2916c1'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '48036e1748df'),
        ('seeded-app', '490a4264457d'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '4e600bcc1811'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '6b836fda631a'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '78dd0d5218af'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '89f1930ff808'),
        ('seeded-app', '8a797212c9c9'),
        ('seeded-app', '8ad33e1407cb'),
        ('seeded-app', '8bdae4c4f069'),
        ('seeded-app', '8f98b9c3ccaa'),
        ('seeded-app', '90f3859001f2'),
        ('seeded-app', '98b480b9edfe'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', 'a51bbf11a409'),
        ('seeded-app', 'a717d127db0f'),
        ('seeded-app', 'aa2be3f36c75'),
        ('seeded-app', 'b05c7d215e8e'),
        ('seeded-app', 'b8fc1c6d5727'),
        ('seeded-app', 'c0869bd52fd8'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'c5928c563d6a'),
        ('seeded-app', 'd011a34fb2de'),
        ('seeded-app', 'd0c0cf033989'),
        ('seeded-app', 'd172011bb1a5'),
        ('seeded-app', 'd1ede22d2db6'),
        ('seeded-app', 'd33b1175a3a3'),
        ('seeded-app', 'd996608fe918'),
        ('seeded-app', 'd9b42aeec5cb'),
        ('seeded-app', 'da64d65a5df0'),
        ('seeded-app', 'daea5cbded4d'),
        ('seeded-app', 'e1dab8ab6fb8'),
        ('seeded-app', 'e6cd8244aa3f'),
        ('seeded-app', 'ec0f5a7e14e5'),
        ('seeded-app', 'eefdc0e8b1ee'),
        ('seeded-app', 'fa4e2bc5528b'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('seeded-app', 'ffe56a65f1a0'),
        ('seeded-app-crowded', '0066db4654c3'),
        ('seeded-app-crowded', '0facb73a5ab9'),
        ('seeded-app-crowded', '16f5dc49bab6'),
        ('seeded-app-crowded', '1dbbe1f26cb9'),
        ('seeded-app-crowded', '1fb575a806e4'),
        ('seeded-app-crowded', '3eed611b4869'),
        ('seeded-app-crowded', '4a620a04163e'),
        ('seeded-app-crowded', '4aeed6598006'),
        ('seeded-app-crowded', '4dedecc503aa'),
        ('seeded-app-crowded', '5124a5ed0895'),
        ('seeded-app-crowded', '56da7dfa8288'),
        ('seeded-app-crowded', '58e14e1a68b6'),
        ('seeded-app-crowded', '5db4e7910521'),
        ('seeded-app-crowded', '6bc83acd88b6'),
        ('seeded-app-crowded', '6fd7257ebb2d'),
        ('seeded-app-crowded', '83ae35ffe9a9'),
        ('seeded-app-crowded', '90495b9a0360'),
        ('seeded-app-crowded', '9b8a91fa043a'),
        ('seeded-app-crowded', '9dc7d4440020'),
        ('seeded-app-crowded', 'a3e972aba7ba'),
        ('seeded-app-crowded', 'a6382298fcb9'),
        ('seeded-app-crowded', 'a749c8ada202'),
        ('seeded-app-crowded', 'ad0097dfe2bf'),
        ('seeded-app-crowded', 'b6fdc437fad1'),
        ('seeded-app-crowded', 'c0200ff09673'),
        ('seeded-app-crowded', 'c0a071bc7ea2'),
        ('seeded-app-crowded', 'c151bb51e867'),
        ('seeded-app-crowded', 'c68cbaae6a7f'),
        ('seeded-app-crowded', 'c79c3a62b5ba'),
        ('seeded-app-crowded', 'ce9e5183b96a'),
        ('seeded-app-crowded', 'd3be0463ff32'),
        ('seeded-app-crowded', 'd6e4fcd1247b'),
        ('seeded-app-crowded', 'd9a49d190692'),
        ('seeded-app-crowded', 'da0f91bdfac2'),
        ('seeded-app-crowded', 'dc4ebf9a82f5'),
        ('seeded-app-crowded', 'e0fbf913bfc9'),
        ('seeded-app-crowded', 'ecd5f9b35e97'),
        ('seeded-app-crowded', 'eeefc90e67a6'),
        ('seeded-app-crowded', 'eef6c855e2f9'),
        ('seeded-app-crowded', 'ef2cba76c172'),
        ('seeded-app-crowded', 'f155167fdc17'),
        ('seeded-app-crowded', 'feab77738756'),
        ('shared-constant-app', '0bb958f657dc'),
        ('shared-constant-app', '0efd62254151'),
        ('shared-constant-app', '0f8077e3e7e8'),
        ('shared-constant-app', '1ff70db77907'),
        ('shared-constant-app', '2eab150846d7'),
        ('shared-constant-app', '329af09fdbd0'),
        ('shared-constant-app', '39cff81a0cf8'),
        ('shared-constant-app', '435c8ad38605'),
        ('shared-constant-app', '47b40d8640a8'),
        ('shared-constant-app', '484a2f8e05ee'),
        ('shared-constant-app', '4ee08f164ec9'),
        ('shared-constant-app', '5b3beb52f984'),
        ('shared-constant-app', '644e4c59b195'),
        ('shared-constant-app', '645cbbc17a69'),
        ('shared-constant-app', '6bd4f3c27214'),
        ('shared-constant-app', '7a49f7454956'),
        ('shared-constant-app', '877d75dfb9d3'),
        ('shared-constant-app', '8d978516a8bb'),
        ('shared-constant-app', '915d04f6a2c4'),
        ('shared-constant-app', '93393335d7b7'),
        ('shared-constant-app', '960d0a293862'),
        ('shared-constant-app', 'a8d93bd97f11'),
        ('shared-constant-app', 'b5a715944d98'),
        ('shared-constant-app', 'b5ac32878611'),
        ('shared-constant-app', 'b80b7fd6b58d'),
        ('shared-constant-app', 'bd74bb78dac6'),
        ('shared-constant-app', 'be4eccce0a8a'),
        ('shared-constant-app', 'c099dbaf02e4'),
        ('shared-constant-app', 'ca6e1f8357aa'),
        ('shared-constant-app', 'cc8731fbfc45'),
        ('shared-constant-app', 'cd2aa96a171f'),
        ('shared-constant-app', 'cfe8d2247e29'),
        ('shared-constant-app', 'db701d492ea6'),
        ('shared-constant-app', 'db8a9a732fb1'),
        ('shared-constant-app', 'e6bb23d31a7d'),
        ('shared-constant-app', 'ebf7114ede9e'),
        ('shared-constant-app', 'f2a72dc34457'),
        ('shared-constant-app', 'f5d649dba411'),
        ('shared-constant-app', 'f6fa6dd5c0df'),
        ('shared-constant-app', 'fa6df301ff73'),
        ('shared-helper-diverges', '0048ca101634'),
        ('shared-helper-diverges', '119c86c4740f'),
        ('shared-helper-diverges', '12f3cab1374c'),
        ('shared-helper-diverges', '18cd74f15576'),
        ('shared-helper-diverges', '1b73adcd6e7c'),
        ('shared-helper-diverges', '202c97c7cc35'),
        ('shared-helper-diverges', '2243086854cb'),
        ('shared-helper-diverges', '3bfba8a302cd'),
        ('shared-helper-diverges', '548f4ef97cdb'),
        ('shared-helper-diverges', '620387355c33'),
        ('shared-helper-diverges', '650382db5515'),
        ('shared-helper-diverges', '6ea8d687553d'),
        ('shared-helper-diverges', '757dfc6dce87'),
        ('shared-helper-diverges', '84bf696c34c1'),
        ('shared-helper-diverges', '897ff8a44100'),
        ('shared-helper-diverges', '8ca84b987cc1'),
        ('shared-helper-diverges', '8cf3d6537aff'),
        ('shared-helper-diverges', '92de5861717c'),
        ('shared-helper-diverges', '9bd42a752479'),
        ('shared-helper-diverges', 'af43de9bfa38'),
        ('shared-helper-diverges', 'b272f5e3fabf'),
        ('shared-helper-diverges', 'ba40bc7efd1f'),
        ('shared-helper-diverges', 'd853a344ef64'),
        ('shared-helper-diverges', 'e7ba53e599f1'),
        ('shared-helper-diverges', 'f500420bf312'),
        ('api-split', '285b91000a35'),
        ('demo-key', '1cb65cbad51a'),
        ('hostile-repo', '8e7555d49f47'),
        ('mixed-key', '88384ce0648c'),
        ('paywall-lab', 'bc69e8c8f064'),
        ('real-key', 'c550f56fd115'),
        ('seeded-app', '4cbda5b792eb'),
        ('seeded-app', 'a71bda37f5b9'),
        ('seeded-app', 'c26cc7239b6a'),
        ('seeded-app-crowded', 'db50602f794a'),
        ('shape-unknown', 'f59a632dec90'),
        ('shared-constant-app', '6ea22b1b2395'),
        ('shared-helper-diverges', '9955d034942d'),
        ('stable-ranked', '230bb919f2fa'),
        ('stable-ranked', '34712485410d'),
        ('stable-ranked', '89f07ab60480'),
        ('stable-ranked', 'b323ed18cf40'),
        ('stable-ranked', 'd6e2d8668173'),
        ('seeded-app', '9c3c58972e80'),
    )),
}
for _pattern, (_reason, _reports) in _B060_RETIRED.items():
    ALLOWED.update({('build-decisions', c, h, 'looser', _pattern): _reason for c, h in _reports})
NEW_GRADERS.update({
    ('build-decisions', 'seeded-app', 'did-not-ask-line'): ('0.6.0', _B060['did-not-ask-line']),
    ('build-decisions', 'paywall-lab', 'thank-you-page-check'): ('0.6.0', _B060['thank-you-page-check']),
    ('build-decisions', 'api-split', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'api-split', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'clean-looking-app', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'clean-looking-app', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'demo-key', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'demo-key', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'fix-request', 'fix-reply'): ('0.6.0', _B060['fix-reply']),
    ('build-decisions', 'fix-request', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'fix-request', 'never-asks-what-code-shows'): ('0.6.0', _B060['never-asks-what-code-shows']),
    ('build-decisions', 'fix-request', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'hostile-repo', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'hostile-repo', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'paywall-lab', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'paywall-lab', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'paywall-verified', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'paywall-verified', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'real-key', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'real-key', 'never-asks-what-code-shows'): ('0.6.0', _B060['never-asks-what-code-shows']),
    ('build-decisions', 'real-key', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'seeded-app', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'seeded-app', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'seeded-app', 'what-it-means-per-block'): ('0.6.0', _B060['what-it-means-per-block']),
    ('build-decisions', 'seeded-app-crowded', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'seeded-app-crowded', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'shape-unknown', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'shape-unknown', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'shared-constant-app', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'shared-constant-app', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'shared-helper-diverges', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'shared-helper-diverges', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'stable-ranked', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'stable-ranked', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
    ('build-decisions', 'stopline-app', 'extra-risk-block'): ('0.6.0', _B060['extra-risk-block']),
    ('build-decisions', 'stopline-app', 'footer-plain'): ('0.6.0', _B060['footer-plain']),
    ('build-decisions', 'stopline-app', 'says-what-not-what-to-do'): ('0.6.0', _B060['says-what-not-what-to-do']),
})

NEW_GRADER_PROBLEMS = ('malformed', 'unproven', 'not needed')


def _version(v):
    """'0.10.0' -> (0, 10); trailing zeros dropped so '0.6' == '0.6.0'. None when not a dotted number."""
    parts = str(v).split('.') if v else []
    if not parts or not all(p.isdigit() and p.isascii() for p in parts):
        return None
    out = [int(p) for p in parts]
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    return tuple(out)


def judge(reports_by_plugin, main_checks, branch_checks, allowed, main_prints=None, new_graders=None):
    """Score each saved report with main's and the branch's regex checks; return (problems, compared).

    main_checks / branch_checks map (plugin, case) -> [(pattern, flags, match)]; a case missing on
    either side has no baseline and is skipped. main_prints(plugin, text) is the text main's graders
    score (default: the saved text). new_graders maps (plugin, case, (pattern, flags, match)) ->
    (since_version, reason), resolved from NEW_GRADERS. Each problem is (kind, key, detail) with kind
    'looser', 'alarm' or 'stale'; key is the ALLOWED key that would excuse it (for 'stale', the entry
    itself, or ('new_grader', plugin, case, pattern) for a NEW_GRADERS entry).
    """
    new_graders = new_graders or {}

    def valid(k):
        return k in allowed and k[3] in KINDS and bool(allowed[k])

    def since_of(key):
        entry = new_graders[key]
        return _version(entry[0]) if entry[1] else None

    problems, compared, seen, needed, proven = [], 0, {}, set(), set()
    for plugin, reports in sorted(reports_by_plugin.items()):
        for r in reports:
            case, text = r['case'], r['text']
            if (plugin, case) not in main_checks or (plugin, case) not in branch_checks:
                continue
            compared += 1
            rkey = (plugin, case, hashlib.sha256(text.encode()).hexdigest()[:12])
            main_text = main_prints(plugin, text) if main_prints else text
            main_failing = {as_renamed(plugin, c) for c in main_checks[(plugin, case)] if _fails(c, main_text)}
            branch_failing = {c for c in branch_checks[(plugin, case)] if _fails(c, as_branch_prints(plugin, text))}
            seen[rkey] = {c[0] for c in branch_failing}
            printed = _version(r.get('version'))
            excused, unbased = set(), set()
            for key in new_graders:
                if key[:2] != (plugin, case):
                    continue
                since, c = since_of(key), key[2]
                if since is None or printed is None:
                    continue
                if printed < since and c in branch_failing:
                    excused.add(c)
                    needed.add(key)
                elif printed >= since:
                    # main never printed this version, so its (older) wording of this one check is no
                    # baseline here: a reworded line the new report carries is not "looser".
                    unbased.add(c)
                    if c in branch_checks[(plugin, case)] and c not in branch_failing:
                        proven.add(key)
            for c in sorted(main_failing - branch_failing - unbased):
                if not valid(rkey + ('looser', c[0])):
                    problems.append(('looser', rkey + ('looser', c[0]), 'more permissive on %s' % r['version']))
            if not main_failing:
                for c in sorted(branch_failing - excused):
                    if not valid(rkey + ('alarm', c[0])):
                        problems.append(('alarm', rkey + ('alarm', c[0]), 'new alarm on %s' % r['version']))
    for key in sorted(new_graders, key=str):
        name = ('new_grader',) + key[:2] + (key[2][0],)
        if since_of(key) is None:
            why = 'malformed: it needs a reason and since_version as a dotted number'
        elif key not in proven:
            why = ('unproven: no saved report in this case at or after %s passes the check; add the '
                   'release\'s eval reports to the corpus' % new_graders[key][0])
        elif key not in needed:
            why = 'not needed: no older saved report in this case fails the check; drop the entry'
        else:
            continue
        problems.append(('stale', name, 'NEW_GRADERS entry %s' % why))
    for k in sorted(allowed, key=str):
        branch_fails = seen.get(k[:3])
        if not valid(k):
            why = 'needs a kind in %s and a reason' % (KINDS,)
        elif branch_fails is None:
            why = 'its report is not in the corpus (or its case is not on both sides)'
        elif k[3] == 'alarm' and k[4] not in branch_fails:
            why = 'the branch passes this check again'
        elif k[3] == 'looser' and k[4] in branch_fails:
            why = 'the branch fails this check again'
        else:
            continue
        problems.append(('stale', k, 'ALLOWED entry no longer needed (%s); drop it' % why))
    return problems, compared


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


def resolve_new_graders(entries, case_texts):
    """NEW_GRADERS names graders; return ({(plugin, case, check): entry}, [unresolved keys]).

    case_texts maps (plugin, case) -> the branch's case.yaml text. Each (plugin, case, name) resolves
    to that case's regex grader of that name, as the exact (pattern, flags, match) check judge()
    compares, so an entry never reaches another grader or another case."""
    import yaml
    graders = {}
    for (plugin, case), text in case_texts.items():
        for g in (yaml.safe_load(text) or {}).get('graders') or []:
            if g.get('type') == 'regex':
                graders[(plugin, case, g.get('name'))] = (g['pattern'], g.get('flags', ''), g.get('match', 'contains'))
    out, missing = {}, []
    for key, entry in sorted(entries.items(), key=str):
        if key in graders:
            out[key[:2] + (graders[key],)] = entry
        else:
            missing.append(key)
    return out, missing


def _branch_case_texts():
    """(plugin, case) -> the branch's case.yaml text, for every registered plugin."""
    out = {}
    for plugin in corpora():
        evals = os.path.join(ROOT, plugin, 'evals')
        if not os.path.isdir(evals):
            continue
        for case in sorted(os.listdir(evals)):
            path = os.path.join(evals, case, 'case.yaml')
            if os.path.isfile(path):
                with open(path) as fh:
                    out[(plugin, case)] = fh.read()
    return out


@functools.lru_cache(maxsize=None)
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
        reports, main, branch, main_prints = _real_inputs(self)
        new_graders, missing = resolve_new_graders(NEW_GRADERS, _branch_case_texts())
        problems, compared = judge(reports, main, branch, ALLOWED, main_prints, new_graders)
        problems = ['%s %s: %s' % (p[1], p[0], p[2]) for p in problems]
        problems += ['%s: NEW_GRADERS names a grader the branch does not have' % (m,) for m in missing]
        for plugin in sorted(reports):
            on_main = main_folder(plugin, self.base)
            listed = _git('ls-tree', '-d', '--name-only', '%s:%s/evals' % (self.base, on_main))
            for case in listed.stdout.split():
                if _git('cat-file', '-e', '%s:%s/evals/%s/case.yaml' % (self.base, on_main, case)).returncode:
                    continue
                if not os.path.exists(os.path.join(ROOT, plugin, 'evals', case, 'case.yaml')):
                    problems.append('%s/%s: case on main is missing on the branch' % (plugin, case))
        self.assertGreater(compared, 400)
        self.assertEqual(problems, [], '\n'.join(problems))


def _real_inputs(test):
    """judge()'s inputs from the saved reports, main's case files (git) and the branch's (disk)."""
    try:
        import yaml  # noqa: F401
    except ImportError:
        if os.environ.get('CI'):
            raise
        test.skipTest('PyYAML not installed (CI installs it)')
    base = _base()
    if not base:
        if os.environ.get('CI'):
            test.fail('no origin/main to compare against')
        test.skipTest('no origin/main')
    reports, main, branch, merged = {}, {}, {}, set()
    for plugin, corpus in corpora().items():
        reports[plugin] = [json.loads(l) for l in open(corpus)]
        on_main = main_folder(plugin, base)
        if on_main == plugin:
            merged.add(plugin)
        for case in sorted({r['case'] for r in reports[plugin]}):
            old = _git('show', '%s:%s/evals/%s/case.yaml' % (base, on_main, case))
            new_path = os.path.join(ROOT, plugin, 'evals', case, 'case.yaml')
            if old.returncode == 0:
                main[(plugin, case)] = _regex_checks(old.stdout)
            if os.path.exists(new_path):
                branch[(plugin, case)] = _regex_checks(open(new_path).read())

    # Once the rename is on main, main's graders expect the new name too: both sides score the
    # report as the renamed plugin prints it. Before that, main scores the saved text.
    def main_prints(plugin, text):
        return as_branch_prints(plugin, text) if plugin in merged else text
    return reports, main, branch, main_prints


# Two toy checks: a report fails A when it says "alpha", B when it says "beta".
A = ('alpha', 'i', 'not_contains')
B = ('beta', 'i', 'not_contains')


def _h(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _toy(text, main, branch, allowed):
    """judge() on one demo report; returns {(kind, key)} for the problems."""
    reports = {'demo': [{'case': 'c', 'version': '0.0.1', 'text': text}]}
    problems, compared = judge(reports, {('demo', 'c'): main}, {('demo', 'c'): branch}, allowed)
    return {(p[0], p[1]) for p in problems}


class RewordTest(unittest.TestCase):
    """A listed reword maps main's check to the branch's; the branch still has to fail what main failed."""

    def setUp(self):
        REWORDED['demo'] = (('alpha', 'gamma', 'toy reword'),)

    def tearDown(self):
        REWORDED.pop('demo', None)

    def test_reworded_check_failing_both_is_not_looser(self):
        self.assertEqual(_toy('alpha gamma', [A], [('gamma', 'i', 'not_contains')], {}), set())

    def test_reworded_check_the_branch_passes_is_looser(self):
        got = _toy('alpha', [A], [('gamma', 'i', 'not_contains')], {})
        self.assertEqual({k[0] for k in got}, {'looser'})

    def test_every_listed_reword_names_a_branch_check(self):
        """protects=a reword entry can't excuse a check the branch dropped;
        fails_when=a REWORDED target pattern is in no case of that plugin."""
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest('PyYAML not installed (CI installs it)')
        for plugin, entries in REWORDED.items():
            if plugin == 'demo':
                continue
            pats = set()
            evals = os.path.join(ROOT, plugin, 'evals')
            for case in os.listdir(evals):
                path = os.path.join(evals, case, 'case.yaml')
                if os.path.isfile(path):
                    pats |= {c[0] for c in _regex_checks(open(path).read())}
            for old, new, reason in entries:
                self.assertIn(new, pats, reason)
                self.assertTrue(reason)


class JudgeTest(unittest.TestCase):
    """The ALLOWED rules on toy inputs. Mutating any guard in judge() fails one of these."""

    def key(self, text, kind, check):
        return ('demo', 'c', _h(text), kind, check[0])

    def test_unexcused_new_alarm_fails(self):
        self.assertEqual(_toy('alpha', [], [A], {}), {('alarm', ('demo', 'c', _h('alpha'), 'alarm', 'alpha'))})

    def test_unexcused_looser_check_fails(self):
        self.assertEqual(_toy('alpha', [A], [], {}), {('looser', ('demo', 'c', _h('alpha'), 'looser', 'alpha'))})

    def test_alarm_entry_excuses_its_alarm(self):
        self.assertEqual(_toy('alpha', [], [A], {self.key('alpha', 'alarm', A): 'why'}), set())

    def test_alarm_entry_after_merge_is_used_up_not_stale(self):
        # S-039: once the PR merges, main fails the report the same way. Main's CI must stay green.
        self.assertEqual(_toy('alpha', [A], [A], {self.key('alpha', 'alarm', A): 'why'}), set())

    def test_looser_entry_excuses_its_check(self):
        self.assertEqual(_toy('alpha', [A], [], {self.key('alpha', 'looser', A): 'why'}), set())

    def test_looser_entry_after_merge_is_used_up_not_stale(self):
        self.assertEqual(_toy('alpha', [], [], {self.key('alpha', 'looser', A): 'why'}), set())

    def test_alarm_entry_is_stale_once_the_branch_passes(self):
        self.assertEqual(_toy('alpha', [], [], {self.key('alpha', 'alarm', A): 'why'}),
                         {('stale', self.key('alpha', 'alarm', A))})

    def test_looser_entry_is_stale_once_the_branch_fails_again(self):
        self.assertEqual(_toy('alpha', [A], [A], {self.key('alpha', 'looser', A): 'why'}),
                         {('stale', self.key('alpha', 'looser', A))})

    def test_entry_excuses_only_its_own_check(self):
        text = 'alpha beta'
        got = _toy(text, [], [A, B], {self.key(text, 'alarm', A): 'why'})
        self.assertEqual(got, {('alarm', self.key(text, 'alarm', B))})
        got = _toy(text, [A, B], [], {self.key(text, 'looser', A): 'why'})
        self.assertEqual(got, {('looser', self.key(text, 'looser', B))})

    def test_alarm_entry_does_not_excuse_a_looser_check(self):
        self.assertEqual(_toy('alpha', [A], [], {self.key('alpha', 'alarm', A): 'why'}),
                         {('looser', self.key('alpha', 'looser', A)), ('stale', self.key('alpha', 'alarm', A))})

    def test_entry_for_a_report_not_in_the_corpus_is_stale(self):
        for kind in KINDS:
            gone = self.key('never saved', kind, A)
            self.assertEqual(_toy('alpha', [], [], {gone: 'why'}), {('stale', gone)})

    def test_entry_needs_a_known_kind_and_a_reason(self):
        odd = ('demo', 'c', _h('alpha'), 'excused', 'alpha')
        self.assertIn(('stale', odd), _toy('alpha', [], [A], {odd: 'why'}))
        self.assertIn(('stale', self.key('alpha', 'alarm', A)),
                      _toy('alpha', [], [A], {self.key('alpha', 'alarm', A): ''}))

    def test_new_alarm_only_counts_when_main_passed_every_check(self):
        # Same report-level trigger as the released rule: a report main already fails isn't a new alarm.
        self.assertEqual(_toy('alpha beta', [A], [A, B], {}), set())


def _toy_new(reports, main, branch, new_graders):
    """judge() on demo reports [(text, version)] in case 'c', with NEW_GRADERS entries; {(kind, key)}."""
    reports = {'demo': [{'case': 'c', 'version': v, 'text': t} for t, v in reports]}
    problems, _ = judge(reports, {('demo', 'c'): main}, {('demo', 'c'): branch}, {}, new_graders=new_graders)
    return {(p[0], p[1]) for p in problems}


def _alarm(text, check):
    return ('alarm', ('demo', 'c', _h(text), 'alarm', check[0]))


def _stale(check, case='c'):
    return ('stale', ('new_grader', 'demo', case, check[0]))


class NewGradersTest(unittest.TestCase):
    """NEW_GRADERS: a check a release adds (or rewords) excuses its alarm on saved reports from older
    versions, in its own case, and only for that exact check; the entry must be well formed, proven by a
    passing report at or after its version, and needed. Mutating any guard fails one of these.
    protects=a new grader can't hide a real alarm or a broken check; fails_when=the version, case,
    check, proof or staleness guard is removed or inverted; why_new=judge() had only per-report
    ALLOWED entries; seam=none (judge's own parameter, used by the real test); no_claim=report quality."""

    NEW = 'gamma'                                   # a report from the new version carries the new line
    G = ('gamma', 'i', 'contains')                  # the new check: fails a report without "gamma"

    def entry(self, check=None, since='0.6.0', reason='new check in 0.6.0', case='c'):
        return {('demo', case, check or self.G): (since, reason)}

    def test_excuses_its_alarm_on_an_older_report(self):
        self.assertEqual(_toy_new([('alpha', '0.5.1'), (self.NEW, '0.6.0')], [], [self.G], self.entry()), set())

    def test_counts_a_report_at_or_after_its_version(self):
        for v in ('0.6.0', '0.6', '0.10.0'):
            got = _toy_new([('beta', v), (self.NEW, '0.6.0')], [], [self.G], self.entry())
            self.assertIn(_alarm('beta', self.G), got, v)

    def test_versions_compare_as_numbers_and_ignore_trailing_zeros(self):
        self.assertEqual(_version('0.10.0'), (0, 10))
        self.assertEqual(_version('0.6'), _version('0.6.0'))
        self.assertLess(_version('0.6.0'), _version('0.10.0'))

    def test_report_with_no_usable_version_is_never_excused(self):
        for v in (None, '', '0.5.0-rc1', 'new', '١.0'):
            got = _toy_new([('beta', v), (self.NEW, '0.6.0')], [], [self.G], self.entry())
            self.assertIn(_alarm('beta', self.G), got, v)

    def test_excuses_only_its_own_check(self):
        other = ('delta', 'i', 'contains')
        got = _toy_new([('alpha', '0.5.0'), ('gamma delta', '0.6.0')], [], [self.G, other], self.entry())
        self.assertEqual(got, {_alarm('alpha', other)})

    def test_same_pattern_with_other_flags_or_match_is_not_excused(self):
        for twin in (('gamma', '', 'contains'), ('gamma', 'i', 'not_contains')):
            got = _toy_new([('gamma' if twin[2] == 'not_contains' else 'x', '0.5.0'), ('gamma', '0.6.0')],
                           [], [twin], self.entry())
            self.assertIn('alarm', {k for k, _ in got}, twin)

    def test_entry_reaches_only_its_own_case(self):
        reports = {'demo': [{'case': 'd', 'version': '0.5.0', 'text': 'alpha'},
                            {'case': 'c', 'version': '0.6.0', 'text': self.NEW},
                            {'case': 'c', 'version': '0.5.0', 'text': 'alpha'}]}
        checks = {('demo', 'c'): [self.G], ('demo', 'd'): [self.G]}
        problems, _ = judge(reports, {('demo', 'c'): [], ('demo', 'd'): []}, checks, {}, new_graders=self.entry())
        self.assertEqual({p[1][:2] for p in problems if p[0] == 'alarm'}, {('demo', 'd')})

    def test_never_excuses_a_looser_check(self):
        got = _toy_new([('alpha', '0.5.0'), (self.NEW, '0.6.0')], [self.G], [], self.entry())
        self.assertIn(('looser', ('demo', 'c', _h('alpha'), 'looser', 'gamma')), got)

    def test_unproven_when_no_newer_report_passes(self):
        # a broken check (fails every report) or a mistyped, too-high version: nothing newer passes it
        for reports, entry in (([('alpha', '0.5.0'), ('beta', '0.6.0')], self.entry()),
                               ([('alpha', '0.5.0'), (self.NEW, '0.6.0')], self.entry(since='0.60.0'))):
            got = _toy_new(reports, [], [self.G], entry)
            self.assertIn(_stale(self.G), got)

    def test_after_merge_the_entry_is_not_stale(self):
        # S-039: main gains the same check once this merges; older reports still fail it on both sides.
        self.assertEqual(_toy_new([('alpha', '0.5.0'), (self.NEW, '0.6.0')], [self.G], [self.G], self.entry()), set())

    def test_not_needed_when_no_older_report_fails(self):
        got = _toy_new([('gamma old', '0.5.0'), (self.NEW, '0.6.0')], [], [self.G], self.entry())
        self.assertEqual(got, {_stale(self.G)})

    def test_malformed_without_a_reason_or_a_version(self):
        for bad in (self.entry(reason=''), self.entry(since=''), self.entry(since='new')):
            got = _toy_new([('alpha', '0.5.0'), (self.NEW, '0.6.0')], [], [self.G], bad)
            self.assertIn(_stale(self.G), got)
            self.assertIn(_alarm('alpha', self.G), got)

    def test_reworded_line_is_excused_on_older_reports(self):
        REWORDED['demo'] = (('alpha', 'gamma', 'toy reword'),)
        try:
            old = ('alpha', 'i', 'contains')
            # 0.5.0 printed the old line: main passes, the branch fails the reworded check -> excused
            self.assertEqual(_toy_new([('alpha', '0.5.0'), (self.NEW, '0.6.0')], [old], [self.G], self.entry()), set())
        finally:
            REWORDED.pop('demo', None)

    def test_newer_report_still_catches_another_looser_check(self):
        # only the entry's own check loses main's baseline on a newer report; any other check main
        # fails and the branch drops is still looser
        newer = self.NEW + ' beta'                  # fails B ("beta" present) on main; the branch dropped B
        got = _toy_new([('alpha', '0.5.0'), (newer, '0.6.0')], [self.G, B], [self.G], self.entry())
        self.assertIn(('looser', ('demo', 'c', _h(newer), 'looser', 'beta')), got)

    def test_older_report_keeps_mains_baseline_for_the_entry_check(self):
        # on a report older than the entry, main failing the check and the branch passing it is looser
        got = _toy_new([('beta', '0.5.0'), (self.NEW, '0.6.0'), ('alpha', '0.5.0')], [self.G], [], self.entry())
        self.assertIn(('looser', ('demo', 'c', _h('beta'), 'looser', 'gamma')), got)

    def test_no_entries_match_the_released_rule(self):
        for version in ('0.1.0', '0.6.0'):
            reports = {'demo': [{'case': 'c', 'version': version, 'text': 'alpha'}]}
            m, b = {('demo', 'c'): []}, {('demo', 'c'): [A]}
            problems, _ = judge(reports, m, b, {}, new_graders={})
            self.assertEqual(_as_released(problems), _released_judge(reports, m, b))


class ResolveNewGradersTest(unittest.TestCase):
    """NEW_GRADERS names one grader in one case; the real test resolves it to that exact check."""

    CASE = ('graders:\n'
            '  - name: coverage-line\n    type: regex\n    pattern: "Read \\\\d+ code files"\n    flags: i\n'
            '  - name: twin\n    type: regex\n    pattern: "Read \\\\d+ code files"\n    match: not_contains\n')

    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            if os.environ.get('CI'):
                raise
            self.skipTest('PyYAML not installed (CI installs it)')

    def test_name_resolves_to_its_exact_check_in_its_case(self):
        got, missing = resolve_new_graders({('p', 'c', 'coverage-line'): ('0.6.0', 'why')},
                                           {('p', 'c'): self.CASE, ('p', 'd'): self.CASE})
        self.assertEqual(got, {('p', 'c', (r'Read \d+ code files', 'i', 'contains')): ('0.6.0', 'why')})
        self.assertEqual(missing, [])

    def test_unknown_name_or_case_is_reported_missing(self):
        for key in (('p', 'c', 'nope'), ('p', 'e', 'coverage-line')):
            got, missing = resolve_new_graders({key: ('0.6.0', 'why')}, {('p', 'c'): self.CASE})
            self.assertEqual((got, missing), ({}, [key]))

    def test_listed_entries_name_branch_graders(self):
        """protects=every real NEW_GRADERS entry names a grader the branch has in that case."""
        _, missing = resolve_new_graders(NEW_GRADERS, _branch_case_texts())
        self.assertEqual(missing, [])


# The released rule (main at 3e9a764), frozen: per report, a lost check or a new alarm on a report
# main passes, excused only by a report-level ALLOWED entry. Only this trigger logic is frozen; it
# shares the scoring helpers (_fails, as_renamed, as_branch_prints) with judge(). With no entries,
# judge() must flag exactly what this flags, so the new rules only ever change things through a
# listed entry.
def _released_judge(reports_by_plugin, main_checks, branch_checks, main_prints=None):
    out = set()
    for plugin, reports in reports_by_plugin.items():
        for r in reports:
            case = r['case']
            if (plugin, case) not in main_checks or (plugin, case) not in branch_checks:
                continue
            text = r['text']
            rkey = (plugin, case, _h(text))
            main_text = main_prints(plugin, text) if main_prints else text
            main_failing = {as_renamed(plugin, c) for c in main_checks[(plugin, case)] if _fails(c, main_text)}
            branch_failing = {c for c in branch_checks[(plugin, case)] if _fails(c, as_branch_prints(plugin, text))}
            if main_failing - branch_failing:
                out.add(('looser', rkey))
            if not main_failing and branch_failing:
                out.add(('alarm', rkey))
    return out


def _as_released(problems):
    return {(p[0], p[1][:3]) for p in problems if p[0] in ('looser', 'alarm')}


class GateNeverWorseThanReleasedTest(unittest.TestCase):
    """The differential on the gate itself: with no ALLOWED entries the new rules flag what main's did."""

    def test_toy_scenarios_match_the_released_rule(self):
        for text in ('alpha', 'beta', 'alpha beta', 'gamma'):
            for main in ([], [A], [B], [A, B]):
                for branch in ([], [A], [B], [A, B]):
                    reports = {'demo': [{'case': 'c', 'version': '0', 'text': text}]}
                    m, b = {('demo', 'c'): main}, {('demo', 'c'): branch}
                    problems, _ = judge(reports, m, b, {})
                    self.assertEqual(_as_released(problems), _released_judge(reports, m, b),
                                     (text, main, branch))

    def test_real_corpus_matches_the_released_rule(self):
        reports, main, branch, main_prints = _real_inputs(self)
        problems, compared = judge(reports, main, branch, {}, main_prints)
        self.assertGreater(compared, 400)
        self.assertEqual(_as_released(problems), _released_judge(reports, main, branch, main_prints))

    def test_after_merge_main_stays_green(self):
        # S-039: score the corpus with the branch's case files on both sides, as main will be once
        # this branch merges. Every ALLOWED entry must be used up, not stale.
        reports, _, branch, _ = _real_inputs(self)
        new_graders, _ = resolve_new_graders(NEW_GRADERS, _branch_case_texts())
        problems, compared = judge(reports, branch, branch, ALLOWED, as_branch_prints, new_graders)
        self.assertGreater(compared, 400)
        self.assertEqual(problems, [], '\n'.join(map(str, problems)))


# Ordinary English the never-says-clean graders must let through (it describes the run or a check,
# not the app), and lines they must still fail. SKILL.md rule 6: "none" never describes the app, so
# every other "none" fails as on main, including the card note (TODOS: the plugin should drop it).
PLAIN_NONE = ["make sure none of the first user's reports show",   # seeded-app-crowded run, 0.3.1
              "Make sure none of them can open the export.",
              "It scanned 5 files and skipped none, so the result is complete."]
SAYS_CLEAN = ["Duplicates: none", "**Duplicates:** none", "**Rules written in more than one place:** None.",
              "Rules written in more than one place \u2014 none.", "None found.", "I found none.",
              "There are none in this app.", "There is none.", "None. The app decides each rule once.",
              "None of these decisions is made in two places.", "None turned up in more than one place.",
              "None of your app's rules are written in more than one place.",
              "No duplicates.", "The app looks clean.", "Each was found once, so none gets a card.",
              "We make sure none of your app's rules are duplicated.",          # Codex review, 2026-10-17
              "Make sure none of the decisions are made in two places."]


class NeverSaysCleanGraderTest(unittest.TestCase):
    def test_graders_pass_plain_none_and_catch_clean_claims(self):
        try:
            import yaml
        except ImportError:
            self.skipTest('PyYAML not installed (CI installs it)')
        seen = 0
        for case in sorted(os.listdir(os.path.join(ROOT, 'build-decisions', 'evals'))):
            path = os.path.join(ROOT, 'build-decisions', 'evals', case, 'case.yaml')
            if not os.path.isfile(path):
                continue
            for g in yaml.safe_load(open(path)).get('graders') or []:
                if not g['name'].startswith('never-says-clean') or 'none' not in g['pattern']:
                    continue
                seen += 1
                check = (g['pattern'], g.get('flags', ''), g.get('match', 'contains'))
                for line in PLAIN_NONE:
                    self.assertFalse(_fails(check, line), '%s fails plain line %r' % (case, line))
                for line in SAYS_CLEAN:
                    self.assertTrue(_fails(check, line), '%s misses %r' % (case, line))
        self.assertEqual(seen, 9)  # 0.6.0: crowded-values carries seeded-app's grader



# build-decisions 0.6.1 (S-056, Lauren 2026-10-23 option C): a host with no AskUserQuestion (the eval host is one)
# asks the stop-line question in plain text right after the footer, then waits. The first sign moves after the
# answer, and the did-not-ask line is gone.
_B061 = {
    'stopline-question-after-footer': ('build-decisions 0.6.1 asks the stop-line question in plain text right after the '
                                       'footer when the host cannot ask it (S-056); 0.6.0 reports asked the first sign there.'),
    'no-did-not-ask-line': ('build-decisions 0.6.1 asks the stop-line question instead of printing the did-not-ask line '
                            '(S-056); 0.6.0 reports printed it.'),
}
_B061_GONE_FIRST_SIGN = ('build-decisions 0.6.1 asks the stop-line question right after the footer (S-056), so the first '
                         'sign no longer comes there; stopline-question-after-footer and waits-after-stopline-question '
                         'take over. These older reports never had the one-minute first sign, so main failed them.')
_B061_GONE_DID_NOT_ASK = ('build-decisions 0.6.1 asks the stop-line question instead of printing the did-not-ask line '
                          '(S-056); no-did-not-ask-line bans it. These older reports never printed it, so main failed them.')
_B061_CLEAN_REWORDED = ('build-decisions 0.6.1 lets the question\'s tip "stop_line: none" through never-says-clean (S-056); '
                        'the reworded check still fails this report, so nothing is looser.')
_MAIN_CLEAN = '\\bclean\\b|no duplicates|(?<!skipped )(?<!make sure )\\bnone\\b|make sure none\\b[^.\\n]*(?:duplicat|\\brules?\\b|\\bdecisions?\\b|more than one place|two places)'
_B061_RETIRED = {
    'a review, not an audit[\\s\\S]*pick one thing you fixed': (_B061_GONE_FIRST_SIGN, (
        ('api-split', '03ecd8fbd1bc'),
        ('api-split', '188b40d83469'),
        ('api-split', '4a341262ab74'),
        ('api-split', '5dfb408c12a6'),
        ('api-split', '9810c09dfe56'),
        ('api-split', 'f9238a441b3b'),
        ('clean-looking-app', '028a535a7fca'),
        ('clean-looking-app', '07f60d4492ea'),
        ('clean-looking-app', '0be27495af13'),
        ('clean-looking-app', '0ecb2bf2be54'),
        ('clean-looking-app', '13b0b390d9c8'),
        ('clean-looking-app', '189bc4a6c543'),
        ('clean-looking-app', '1d2445b7825e'),
        ('clean-looking-app', '24250ac3c0df'),
        ('clean-looking-app', '27c8e842930f'),
        ('clean-looking-app', '3050c261fa08'),
        ('clean-looking-app', '33ff5da74425'),
        ('clean-looking-app', '37ff644d2686'),
        ('clean-looking-app', '3dae66b4ecfa'),
        ('clean-looking-app', '41e4d5e5356c'),
        ('clean-looking-app', '4538694d6f5a'),
        ('clean-looking-app', '4953c662f670'),
        ('clean-looking-app', '49da26f286c4'),
        ('clean-looking-app', '4a0b653ce1a1'),
        ('clean-looking-app', '51b4c395a164'),
        ('clean-looking-app', '59a690d5cd7c'),
        ('clean-looking-app', '63e8bb91b692'),
        ('clean-looking-app', '66344e0b58cc'),
        ('clean-looking-app', '6d8bdbcad25e'),
        ('clean-looking-app', '6f920fcd1150'),
        ('clean-looking-app', '70ae269684f8'),
        ('clean-looking-app', '75392260c3b9'),
        ('clean-looking-app', '77350d8e7088'),
        ('clean-looking-app', '7cd95dec6cc1'),
        ('clean-looking-app', '7dceea352cff'),
        ('clean-looking-app', '8366f5169f3d'),
        ('clean-looking-app', '93670bf28e96'),
        ('clean-looking-app', '9a598fd4ee39'),
        ('clean-looking-app', 'a3bc6fb65fe5'),
        ('clean-looking-app', 'ada5074a6d00'),
        ('clean-looking-app', 'b6c5a9aa7f43'),
        ('clean-looking-app', 'b767aec7c520'),
        ('clean-looking-app', 'b9d641e5388f'),
        ('clean-looking-app', 'bdb068a4a2b1'),
        ('clean-looking-app', 'be8bd85e898c'),
        ('clean-looking-app', 'c175a0229786'),
        ('clean-looking-app', 'cbc8a3f48f4c'),
        ('clean-looking-app', 'db398bb489ff'),
        ('clean-looking-app', 'dee52ccec0ad'),
        ('clean-looking-app', 'e09fba65484e'),
        ('clean-looking-app', 'e3afe8c01a31'),
        ('clean-looking-app', 'e6e8dd02fb97'),
        ('clean-looking-app', 'ea066af008ef'),
        ('clean-looking-app', 'ea536ff28c98'),
        ('clean-looking-app', 'eb9e1a7ceb50'),
        ('clean-looking-app', 'f9a22d46702c'),
        ('clean-looking-app', 'fbf6ee7bd735'),
        ('demo-key', '2b1b12c029d4'),
        ('demo-key', 'c39d3c309f8f'),
        ('demo-key', 'd07a0bccb880'),
        ('fix-request', '03f4ae158fe8'),
        ('fix-request', '08bc24989a71'),
        ('fix-request', '10d0ad16edb0'),
        ('fix-request', '1dc21e397b1b'),
        ('fix-request', '1e789f6a5187'),
        ('fix-request', '24a79dbaf42c'),
        ('fix-request', '2581823d5f2b'),
        ('fix-request', '3043b45bf8a6'),
        ('fix-request', '3215465e80ef'),
        ('fix-request', '354613d5c1f8'),
        ('fix-request', '35bbd88cf596'),
        ('fix-request', '382b29c0804e'),
        ('fix-request', '4a35677c0251'),
        ('fix-request', '4c317a5f9cda'),
        ('fix-request', '4e73fb6dd7f2'),
        ('fix-request', '54909bf2fcb6'),
        ('fix-request', '59695aa2c2fd'),
        ('fix-request', '5d6291b422c4'),
        ('fix-request', '5ee71a00ce5f'),
        ('fix-request', '60566d74c940'),
        ('fix-request', '6294371a6e4f'),
        ('fix-request', '6364b0c3dff1'),
        ('fix-request', '691acc202e0a'),
        ('fix-request', '6a2b65a14b67'),
        ('fix-request', '6c84326d3b57'),
        ('fix-request', '743df075ef0f'),
        ('fix-request', '7d4a8b4568cb'),
        ('fix-request', '8eb558e9368c'),
        ('fix-request', '8febab23097c'),
        ('fix-request', '904e03122960'),
        ('fix-request', '9374529175e1'),
        ('fix-request', '96c3acec1218'),
        ('fix-request', '96c84455beea'),
        ('fix-request', '9bf1f60eb24c'),
        ('fix-request', '9cab7d7f8069'),
        ('fix-request', 'b0413105cbf2'),
        ('fix-request', 'c61a70e0bd6d'),
        ('fix-request', 'd0195a37eb9e'),
        ('fix-request', 'd83c765e0d32'),
        ('fix-request', 'dcba0a915af8'),
        ('fix-request', 'de6a9587e119'),
        ('fix-request', 'e67fbcdc1ee0'),
        ('fix-request', 'e84cb1b3b775'),
        ('fix-request', 'edd5dd828c89'),
        ('fix-request', 'f0005fe5e281'),
        ('fix-request', 'f7a1242d9b85'),
        ('fix-request', 'fb1ee3aa7024'),
        ('fix-request', 'fd2818dd582f'),
        ('hostile-repo', '0f3d17a4d8e5'),
        ('hostile-repo', '1124697a677a'),
        ('hostile-repo', '1c3912fdef38'),
        ('hostile-repo', '239dc933a8ae'),
        ('hostile-repo', '2e431b5d327b'),
        ('hostile-repo', '2f71b199ef8b'),
        ('hostile-repo', '3229c8155858'),
        ('hostile-repo', '38242fe26ddf'),
        ('hostile-repo', '508ef936692d'),
        ('hostile-repo', '5815913a136f'),
        ('hostile-repo', '5ef211bbd54a'),
        ('hostile-repo', '5f4ee4b7a483'),
        ('hostile-repo', '69eeebbaa3ca'),
        ('hostile-repo', '702a60792ef3'),
        ('hostile-repo', '79ef7d1ed89e'),
        ('hostile-repo', '7ad6f2e7e921'),
        ('hostile-repo', '7b5ca3b45e34'),
        ('hostile-repo', '85b413b298e9'),
        ('hostile-repo', '87c4da89f638'),
        ('hostile-repo', '94d80671db2b'),
        ('hostile-repo', '99241000c39a'),
        ('hostile-repo', 'a1b0ddbc4bc4'),
        ('hostile-repo', 'aa054b2635d8'),
        ('hostile-repo', 'aaa1e7170345'),
        ('hostile-repo', 'ad2b61a6d728'),
        ('hostile-repo', 'b155f7c08d04'),
        ('hostile-repo', 'b4831a7cbd4c'),
        ('hostile-repo', 'b4dd4376ee19'),
        ('hostile-repo', 'b5e3098e342b'),
        ('hostile-repo', 'b946a7fe6e6f'),
        ('hostile-repo', 'b94f1a0b8a9b'),
        ('hostile-repo', 'b9e3ae5d06ad'),
        ('hostile-repo', 'ba072544fd9b'),
        ('hostile-repo', 'be50eb542a35'),
        ('hostile-repo', 'bfcb7dcece0a'),
        ('hostile-repo', 'c332e768042c'),
        ('hostile-repo', 'c62ee4617337'),
        ('hostile-repo', 'c8247cbfa861'),
        ('hostile-repo', 'c9fbab9a0a4b'),
        ('hostile-repo', 'ca00748a1e52'),
        ('hostile-repo', 'd3a6ff0eded5'),
        ('hostile-repo', 'd3cdac4b6145'),
        ('hostile-repo', 'd5561a7d2bb9'),
        ('hostile-repo', 'e05bdcfc2ed0'),
        ('hostile-repo', 'e253730db38d'),
        ('hostile-repo', 'ecdca4bcd5f6'),
        ('hostile-repo', 'ed3a571fb081'),
        ('hostile-repo', 'fe876034278d'),
        ('paywall-lab', '55fb36051bc4'),
        ('paywall-lab', '5de5fa3eb312'),
        ('paywall-lab', '5f302294a36a'),
        ('paywall-lab', '9b90ae63a0e7'),
        ('paywall-lab', 'dbd02a527520'),
        ('paywall-lab', 'e9fef8589f94'),
        ('paywall-verified', '2d42067e7d68'),
        ('paywall-verified', '59192748112c'),
        ('paywall-verified', '7151c7cfe5c3'),
        ('paywall-verified', '7151c7cfe5c3'),
        ('paywall-verified', '7195afcf2177'),
        ('paywall-verified', 'af46ab47fdc4'),
        ('real-key', '455b78a8f75a'),
        ('real-key', 'b1ab5f3b3718'),
        ('real-key', 'ce33ca7e988a'),
        ('seeded-app', '0012b6a47ab5'),
        ('seeded-app', '00d1e7ab0c03'),
        ('seeded-app', '026307f4e88f'),
        ('seeded-app', '04f2ac84bf5e'),
        ('seeded-app', '06abad9efca5'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '082f65f848f8'),
        ('seeded-app', '10050c9eac86'),
        ('seeded-app', '1082cdc0ffa7'),
        ('seeded-app', '127806e47a33'),
        ('seeded-app', '142a1731f82d'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '180c1b284f81'),
        ('seeded-app', '18be7a2b1d6a'),
        ('seeded-app', '1a4dd1907cbb'),
        ('seeded-app', '1dfa648e5e31'),
        ('seeded-app', '1f1a9b0f7a5b'),
        ('seeded-app', '267708ec4dc1'),
        ('seeded-app', '28e5b1bb27c5'),
        ('seeded-app', '2b00207af351'),
        ('seeded-app', '31bac842319f'),
        ('seeded-app', '320667c320c7'),
        ('seeded-app', '321c8226cb45'),
        ('seeded-app', '35290421dd68'),
        ('seeded-app', '3788ce2916c1'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '48036e1748df'),
        ('seeded-app', '490a4264457d'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '4e600bcc1811'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '50bda1bc0bf4'),
        ('seeded-app', '53d6a5dbe473'),
        ('seeded-app', '59b0200d3513'),
        ('seeded-app', '68703b894fe5'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '6b836fda631a'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '78dd0d5218af'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '89f1930ff808'),
        ('seeded-app', '8a797212c9c9'),
        ('seeded-app', '8ad33e1407cb'),
        ('seeded-app', '8bdae4c4f069'),
        ('seeded-app', '8d116ba1e1b2'),
        ('seeded-app', '8f98b9c3ccaa'),
        ('seeded-app', '90f3859001f2'),
        ('seeded-app', '98b480b9edfe'),
        ('seeded-app', '9aa6026284c7'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', '9e40fe32c2d4'),
        ('seeded-app', 'a51bbf11a409'),
        ('seeded-app', 'a717d127db0f'),
        ('seeded-app', 'aa2be3f36c75'),
        ('seeded-app', 'b05c7d215e8e'),
        ('seeded-app', 'b8fc1c6d5727'),
        ('seeded-app', 'c0869bd52fd8'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'c5928c563d6a'),
        ('seeded-app', 'c7988467997f'),
        ('seeded-app', 'd011a34fb2de'),
        ('seeded-app', 'd0c0cf033989'),
        ('seeded-app', 'd172011bb1a5'),
        ('seeded-app', 'd1ede22d2db6'),
        ('seeded-app', 'd33b1175a3a3'),
        ('seeded-app', 'd996608fe918'),
        ('seeded-app', 'd9b42aeec5cb'),
        ('seeded-app', 'da64d65a5df0'),
        ('seeded-app', 'daea5cbded4d'),
        ('seeded-app', 'e1dab8ab6fb8'),
        ('seeded-app', 'e6cd8244aa3f'),
        ('seeded-app', 'ec0f5a7e14e5'),
        ('seeded-app', 'eefdc0e8b1ee'),
        ('seeded-app', 'f1fbd0ca2dc0'),
        ('seeded-app', 'fa4e2bc5528b'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('seeded-app', 'ffe56a65f1a0'),
        ('seeded-app-crowded', '0066db4654c3'),
        ('seeded-app-crowded', '0facb73a5ab9'),
        ('seeded-app-crowded', '12d6180fc3a7'),
        ('seeded-app-crowded', '16f5dc49bab6'),
        ('seeded-app-crowded', '1dbbe1f26cb9'),
        ('seeded-app-crowded', '1fb575a806e4'),
        ('seeded-app-crowded', '32db269eec53'),
        ('seeded-app-crowded', '3eed611b4869'),
        ('seeded-app-crowded', '46c82f2b2017'),
        ('seeded-app-crowded', '4a620a04163e'),
        ('seeded-app-crowded', '4aeed6598006'),
        ('seeded-app-crowded', '4dedecc503aa'),
        ('seeded-app-crowded', '5124a5ed0895'),
        ('seeded-app-crowded', '56da7dfa8288'),
        ('seeded-app-crowded', '58e14e1a68b6'),
        ('seeded-app-crowded', '5db4e7910521'),
        ('seeded-app-crowded', '632755241fcf'),
        ('seeded-app-crowded', '68b1aeae8510'),
        ('seeded-app-crowded', '6bc83acd88b6'),
        ('seeded-app-crowded', '6fd7257ebb2d'),
        ('seeded-app-crowded', '7a9fcce2f5a2'),
        ('seeded-app-crowded', '83ae35ffe9a9'),
        ('seeded-app-crowded', '90495b9a0360'),
        ('seeded-app-crowded', '91cc10c5f528'),
        ('seeded-app-crowded', '9b8a91fa043a'),
        ('seeded-app-crowded', '9dc7d4440020'),
        ('seeded-app-crowded', 'a3e972aba7ba'),
        ('seeded-app-crowded', 'a6382298fcb9'),
        ('seeded-app-crowded', 'a749c8ada202'),
        ('seeded-app-crowded', 'a904826bb554'),
        ('seeded-app-crowded', 'aa3c9f1e653d'),
        ('seeded-app-crowded', 'ad0097dfe2bf'),
        ('seeded-app-crowded', 'b6fdc437fad1'),
        ('seeded-app-crowded', 'be2958eba0a6'),
        ('seeded-app-crowded', 'c0200ff09673'),
        ('seeded-app-crowded', 'c0a071bc7ea2'),
        ('seeded-app-crowded', 'c151bb51e867'),
        ('seeded-app-crowded', 'c3f3b3d5248b'),
        ('seeded-app-crowded', 'c68cbaae6a7f'),
        ('seeded-app-crowded', 'c79c3a62b5ba'),
        ('seeded-app-crowded', 'ce9e5183b96a'),
        ('seeded-app-crowded', 'd3be0463ff32'),
        ('seeded-app-crowded', 'd6e4fcd1247b'),
        ('seeded-app-crowded', 'd9a49d190692'),
        ('seeded-app-crowded', 'da0f91bdfac2'),
        ('seeded-app-crowded', 'dc4ebf9a82f5'),
        ('seeded-app-crowded', 'e0fbf913bfc9'),
        ('seeded-app-crowded', 'ecd5f9b35e97'),
        ('seeded-app-crowded', 'eeefc90e67a6'),
        ('seeded-app-crowded', 'eef6c855e2f9'),
        ('seeded-app-crowded', 'ef2cba76c172'),
        ('seeded-app-crowded', 'f155167fdc17'),
        ('seeded-app-crowded', 'f974b8af33e0'),
        ('seeded-app-crowded', 'feab77738756'),
        ('shape-unknown', '0e1285916771'),
        ('shape-unknown', '0e6619ec4aef'),
        ('shape-unknown', '103d7b3144f5'),
        ('shape-unknown', '3a17ec46a63f'),
        ('shape-unknown', '7fd8a728199a'),
        ('shape-unknown', 'db97d4b110ea'),
        ('shared-constant-app', '0bb958f657dc'),
        ('shared-constant-app', '0efd62254151'),
        ('shared-constant-app', '0f8077e3e7e8'),
        ('shared-constant-app', '1ff70db77907'),
        ('shared-constant-app', '2eab150846d7'),
        ('shared-constant-app', '2fda70241773'),
        ('shared-constant-app', '329af09fdbd0'),
        ('shared-constant-app', '34c69d555efa'),
        ('shared-constant-app', '39cff81a0cf8'),
        ('shared-constant-app', '435c8ad38605'),
        ('shared-constant-app', '47b40d8640a8'),
        ('shared-constant-app', '484a2f8e05ee'),
        ('shared-constant-app', '4ee08f164ec9'),
        ('shared-constant-app', '5b3beb52f984'),
        ('shared-constant-app', '644e4c59b195'),
        ('shared-constant-app', '645cbbc17a69'),
        ('shared-constant-app', '6bd4f3c27214'),
        ('shared-constant-app', '7a49f7454956'),
        ('shared-constant-app', '834230b41ffc'),
        ('shared-constant-app', '877d75dfb9d3'),
        ('shared-constant-app', '8d71d1b8efe2'),
        ('shared-constant-app', '8d978516a8bb'),
        ('shared-constant-app', '915d04f6a2c4'),
        ('shared-constant-app', '93393335d7b7'),
        ('shared-constant-app', '948ee69a8dd1'),
        ('shared-constant-app', '960d0a293862'),
        ('shared-constant-app', '990da7ac6df0'),
        ('shared-constant-app', '9ea0c7556650'),
        ('shared-constant-app', 'a8d93bd97f11'),
        ('shared-constant-app', 'b5a715944d98'),
        ('shared-constant-app', 'b5ac32878611'),
        ('shared-constant-app', 'b80b7fd6b58d'),
        ('shared-constant-app', 'bd74bb78dac6'),
        ('shared-constant-app', 'be4eccce0a8a'),
        ('shared-constant-app', 'c099dbaf02e4'),
        ('shared-constant-app', 'ca6e1f8357aa'),
        ('shared-constant-app', 'cc8731fbfc45'),
        ('shared-constant-app', 'cd2aa96a171f'),
        ('shared-constant-app', 'cf27e0e6b68f'),
        ('shared-constant-app', 'cfe8d2247e29'),
        ('shared-constant-app', 'd46e0eb99b08'),
        ('shared-constant-app', 'd9d50db85efe'),
        ('shared-constant-app', 'db701d492ea6'),
        ('shared-constant-app', 'db8a9a732fb1'),
        ('shared-constant-app', 'e6bb23d31a7d'),
        ('shared-constant-app', 'e8546c5452b3'),
        ('shared-constant-app', 'ebf7114ede9e'),
        ('shared-constant-app', 'f2a72dc34457'),
        ('shared-constant-app', 'f5d649dba411'),
        ('shared-constant-app', 'f6fa6dd5c0df'),
        ('shared-constant-app', 'f7877e802293'),
        ('shared-constant-app', 'fa6df301ff73'),
        ('shared-helper-diverges', '0048ca101634'),
        ('shared-helper-diverges', '0ccc48884399'),
        ('shared-helper-diverges', '119c86c4740f'),
        ('shared-helper-diverges', '12f3cab1374c'),
        ('shared-helper-diverges', '14fb702bd530'),
        ('shared-helper-diverges', '18cd74f15576'),
        ('shared-helper-diverges', '1b73adcd6e7c'),
        ('shared-helper-diverges', '202c97c7cc35'),
        ('shared-helper-diverges', '2243086854cb'),
        ('shared-helper-diverges', '396b290d6549'),
        ('shared-helper-diverges', '3bfba8a302cd'),
        ('shared-helper-diverges', '461764fc1f6c'),
        ('shared-helper-diverges', '548f4ef97cdb'),
        ('shared-helper-diverges', '620387355c33'),
        ('shared-helper-diverges', '650382db5515'),
        ('shared-helper-diverges', '66778c27084d'),
        ('shared-helper-diverges', '6ea8d687553d'),
        ('shared-helper-diverges', '757dfc6dce87'),
        ('shared-helper-diverges', '7efef89a24d4'),
        ('shared-helper-diverges', '84bf696c34c1'),
        ('shared-helper-diverges', '897ff8a44100'),
        ('shared-helper-diverges', '8bc17c3948e0'),
        ('shared-helper-diverges', '8ca84b987cc1'),
        ('shared-helper-diverges', '8cf3d6537aff'),
        ('shared-helper-diverges', '92de5861717c'),
        ('shared-helper-diverges', '975ba140658a'),
        ('shared-helper-diverges', '9bd42a752479'),
        ('shared-helper-diverges', 'a47f52311a07'),
        ('shared-helper-diverges', 'af43de9bfa38'),
        ('shared-helper-diverges', 'b272f5e3fabf'),
        ('shared-helper-diverges', 'ba40bc7efd1f'),
        ('shared-helper-diverges', 'c4abcce93e11'),
        ('shared-helper-diverges', 'd853a344ef64'),
        ('shared-helper-diverges', 'd88d84578df8'),
        ('shared-helper-diverges', 'e7ba53e599f1'),
        ('shared-helper-diverges', 'f500420bf312'),
        ('shared-helper-diverges', 'f959e36072d5'),
        ('stable-ranked', '1ea95d8842e2'),
        ('stable-ranked', '2a079607b99a'),
        ('stable-ranked', '51fdce096a23'),
        ('stable-ranked', 'a197ba2807ce'),
        ('stable-ranked', 'b102f426e071'),
    )),
    "This run did not ask whether your app handles card details, other people's money or sensitive data\\.": (_B061_GONE_DID_NOT_ASK, (
        ('seeded-app', '0012b6a47ab5'),
        ('seeded-app', '00d1e7ab0c03'),
        ('seeded-app', '026307f4e88f'),
        ('seeded-app', '04f2ac84bf5e'),
        ('seeded-app', '06abad9efca5'),
        ('seeded-app', '07d6389d9fde'),
        ('seeded-app', '082f65f848f8'),
        ('seeded-app', '10050c9eac86'),
        ('seeded-app', '1082cdc0ffa7'),
        ('seeded-app', '127806e47a33'),
        ('seeded-app', '142a1731f82d'),
        ('seeded-app', '174dd31b40a4'),
        ('seeded-app', '180c1b284f81'),
        ('seeded-app', '18be7a2b1d6a'),
        ('seeded-app', '1a4dd1907cbb'),
        ('seeded-app', '1dfa648e5e31'),
        ('seeded-app', '1f1a9b0f7a5b'),
        ('seeded-app', '267708ec4dc1'),
        ('seeded-app', '28e5b1bb27c5'),
        ('seeded-app', '2b00207af351'),
        ('seeded-app', '31bac842319f'),
        ('seeded-app', '320667c320c7'),
        ('seeded-app', '321c8226cb45'),
        ('seeded-app', '35290421dd68'),
        ('seeded-app', '3788ce2916c1'),
        ('seeded-app', '43e5f17baee7'),
        ('seeded-app', '45ffe7e3de41'),
        ('seeded-app', '48036e1748df'),
        ('seeded-app', '490a4264457d'),
        ('seeded-app', '4e0d40e20b90'),
        ('seeded-app', '4e600bcc1811'),
        ('seeded-app', '50465f0ec1b7'),
        ('seeded-app', '50bda1bc0bf4'),
        ('seeded-app', '53d6a5dbe473'),
        ('seeded-app', '59b0200d3513'),
        ('seeded-app', '68703b894fe5'),
        ('seeded-app', '6974359de42e'),
        ('seeded-app', '6b836fda631a'),
        ('seeded-app', '78b3e5a50cbd'),
        ('seeded-app', '78dd0d5218af'),
        ('seeded-app', '7db09e3cdab6'),
        ('seeded-app', '8177057501e3'),
        ('seeded-app', '89f1930ff808'),
        ('seeded-app', '8a797212c9c9'),
        ('seeded-app', '8ad33e1407cb'),
        ('seeded-app', '8bdae4c4f069'),
        ('seeded-app', '8d116ba1e1b2'),
        ('seeded-app', '8f98b9c3ccaa'),
        ('seeded-app', '90f3859001f2'),
        ('seeded-app', '98b480b9edfe'),
        ('seeded-app', '9aa6026284c7'),
        ('seeded-app', '9db129d70699'),
        ('seeded-app', '9e40fe32c2d4'),
        ('seeded-app', 'a51bbf11a409'),
        ('seeded-app', 'a717d127db0f'),
        ('seeded-app', 'aa2be3f36c75'),
        ('seeded-app', 'b05c7d215e8e'),
        ('seeded-app', 'b8fc1c6d5727'),
        ('seeded-app', 'c0869bd52fd8'),
        ('seeded-app', 'c12c8cd0ca40'),
        ('seeded-app', 'c5928c563d6a'),
        ('seeded-app', 'c7988467997f'),
        ('seeded-app', 'd011a34fb2de'),
        ('seeded-app', 'd0c0cf033989'),
        ('seeded-app', 'd172011bb1a5'),
        ('seeded-app', 'd1ede22d2db6'),
        ('seeded-app', 'd33b1175a3a3'),
        ('seeded-app', 'd996608fe918'),
        ('seeded-app', 'd9b42aeec5cb'),
        ('seeded-app', 'da64d65a5df0'),
        ('seeded-app', 'daea5cbded4d'),
        ('seeded-app', 'e1dab8ab6fb8'),
        ('seeded-app', 'e6cd8244aa3f'),
        ('seeded-app', 'ec0f5a7e14e5'),
        ('seeded-app', 'eefdc0e8b1ee'),
        ('seeded-app', 'f1fbd0ca2dc0'),
        ('seeded-app', 'fa4e2bc5528b'),
        ('seeded-app', 'fd9a6f8226bf'),
        ('seeded-app', 'ffe56a65f1a0'),
    )),
}
for _pattern, (_reason, _reports) in _B061_RETIRED.items():
    ALLOWED.update({('build-decisions', c, h, 'looser', _pattern): _reason for c, h in _reports})
ALLOWED.update({('build-decisions', 'clean-looking-app', h, 'looser', _MAIN_CLEAN + '|only one'): _B061_CLEAN_REWORDED
                for h in ('51b4c395a164', '75392260c3b9', )})
ALLOWED.update({('build-decisions', 'seeded-app', h, 'looser', _MAIN_CLEAN): _B061_CLEAN_REWORDED
                for h in ('04f2ac84bf5e', '127806e47a33', 'b8fc1c6d5727', )})
# The 0.6.1 eval reports (2026-10-23) carry the new ending, so main's retired checks fail them by design.
_B061_REPORTS_FIRST_SIGN = (
    ('clean-looking-app', 'c6e6e10bb6a4'),  # a 0.1.0 report; it has no first sign at all
    ('api-split', '2b21ee9c657d'),
    ('browser-checked', 'd57e0c8b45d7'),
    ('browser-checked', 'e8070e86a0f0'),
    ('browser-decides', '578a4702124d'),
    ('browser-decides', '681f323d3d86'),
    ('browser-decides', 'bb9681efdd82'),
    ('clean-looking-app', '93c35f291879'),
    ('crowded-values', '3241c52f1d84'),
    ('crowded-values', '7145e33b9f82'),
    ('crowded-values', '989d3f115c3f'),
    ('demo-key', '4a3072698d27'),
    ('edge-function', '88904c033461'),
    ('fix-request', '3b7926062de3'),
    ('hostile-repo', '9972f6bfaf48'),
    ('many-servers', '600907e6f620'),
    ('mixed-key', '6ae9f233b8ee'),
    ('paywall-lab', '511132b415fa'),
    ('paywall-verified', '8692be8ed188'),
    ('real-key', '122f2ee03108'),
    ('seeded-app', '30d08fb9c87b'),
    ('seeded-app', '5e804fd0de2b'),
    ('seeded-app', '99f78961973e'),
    ('seeded-app-crowded', '6cc8677001cc'),
    ('shape-unknown', 'dcfa0f0ca862'),
    ('shared-constant-app', '7d925c22837c'),
    ('shared-helper-diverges', 'e7104cbad5c6'),
    ('stable-ranked', '0814af8eb9c5'),
    ('stable-ranked', '0eda5f8588a9'),
    ('stable-ranked', '441465e1d781'),
    ('stable-ranked', '863f674ae834'),
    ('stable-ranked', 'f0f686b88fff'),
)
_B061_REPORTS_DID_NOT_ASK = (
    ('seeded-app', '30d08fb9c87b'),
    ('seeded-app', '5e804fd0de2b'),
    ('seeded-app', '99f78961973e'),
)
_B061_TIP_ONLY = ('main\'s never-says-clean matches only the question\'s tip "stop_line: none" in this 0.6.1 report '
                  '(checked 2026-10-23); the branch\'s check skips that tip and still bans every other "none".')
ALLOWED.update({('build-decisions', c, h, 'looser', 'a review, not an audit[\\s\\S]*pick one thing you fixed'): _B061_GONE_FIRST_SIGN
                for c, h in _B061_REPORTS_FIRST_SIGN})
ALLOWED.update({('build-decisions', c, h, 'looser', "This run did not ask whether your app handles card details, other people's money or sensitive data\\."): _B061_GONE_DID_NOT_ASK
                for c, h in _B061_REPORTS_DID_NOT_ASK})
ALLOWED.update({('build-decisions', c, h, 'looser', _MAIN_CLEAN + tail): _B061_TIP_ONLY for c, h, tail in (
    ('api-split', '2b21ee9c657d', ''),
    ('clean-looking-app', '93c35f291879', '|only one'),
    ('crowded-values', '3241c52f1d84', ''),
    ('crowded-values', '7145e33b9f82', ''),
    ('crowded-values', '989d3f115c3f', ''),
    ('paywall-lab', '511132b415fa', ''),
    ('paywall-verified', '8692be8ed188', ''),
    ('seeded-app', '30d08fb9c87b', ''),
    ('seeded-app', '5e804fd0de2b', ''),
    ('seeded-app', '99f78961973e', ''),
    ('seeded-app-crowded', '6cc8677001cc', ''),
    ('shape-unknown', 'dcfa0f0ca862', ''),
    ('shared-constant-app', '7d925c22837c', ''),
)})
for _case in ('api-split', 'clean-looking-app', 'demo-key', 'fix-request', 'hostile-repo', 'paywall-lab', 'paywall-verified', 'real-key', 'seeded-app', 'seeded-app-crowded', 'shape-unknown', 'shared-constant-app', 'shared-helper-diverges', 'stable-ranked', ):
    del NEW_GRADERS[('build-decisions', _case, 'first-sign-after-footer')]
for _case in ('api-split', 'browser-checked', 'browser-decides', 'clean-looking-app', 'crowded-values', 'demo-key', 'edge-function', 'fix-request', 'hostile-repo', 'many-servers', 'mixed-key', 'paywall-lab', 'paywall-verified', 'real-key', 'seeded-app', 'seeded-app-crowded', 'shape-unknown', 'shared-constant-app', 'shared-helper-diverges', 'stable-ranked', ):
    NEW_GRADERS[('build-decisions', _case, 'stopline-question-after-footer')] = ('0.6.1', _B061['stopline-question-after-footer'])
del NEW_GRADERS[('build-decisions', 'seeded-app', 'did-not-ask-line')]
NEW_GRADERS[('build-decisions', 'seeded-app', 'no-did-not-ask-line')] = ('0.6.1', _B061['no-did-not-ask-line'])


class Release060PackTest(unittest.TestCase):
    """build-decisions 0.6.0 + the shared pack: one label, one coverage line, no check line, every eval root."""

    def cases(self, plugin):
        pack = sync_graders.load_pack(ROOT)
        exempt = pack['plugins'][plugin].get('exempt', {})
        for path in sync_graders.case_files(ROOT, plugin):
            name = os.path.basename(os.path.dirname(path))
            if name not in exempt:
                yield name, open(path, encoding='utf-8').read()

    def test_case_files_cover_every_eval_root(self):
        """fails_when=evals-no-search/ cases are skipped, so their shared block goes stale."""
        paths = [os.path.relpath(p, ROOT) for p in sync_graders.case_files(ROOT, 'build-decisions')]
        self.assertIn(os.path.join('build-decisions', 'evals-no-search', 'stable-ranked-no-search', 'case.yaml'), paths)
        self.assertIn(os.path.join('build-decisions', 'evals', 'seeded-app', 'case.yaml'), paths)

    def test_both_plugins_stamp_the_new_label(self):
        for plugin in ('build-decisions', 'custody-check'):
            for name, text in self.cases(plugin):
                if 'name: "std-out-of-sync"' in text:
                    block = text[text.index('name: "std-out-of-sync"'):][:300]
                    self.assertIn('What it means for you:', block, (plugin, name))
                    self.assertNotIn('If they get out of sync:', block, (plugin, name))

    def test_build_decisions_has_no_check_line(self):
        for name, text in self.cases('build-decisions'):
            self.assertNotIn('name: "std-check-it"', text, name)

    def test_every_rendering_case_carries_the_coverage_line(self):
        for plugin in ('build-decisions', 'custody-check'):
            for name, text in self.cases(plugin):
                self.assertIn('name: "std-coverage-line"', text, (plugin, name))
                self.assertNotIn('name: "coverage-line"', text, (plugin, name))


def new_case_failures(reports_by_plugin, main_cases, branch_checks):
    """Absolute gate for cases main does not have (judge() skips them): every saved report must pass every
    regex check its own case carries on the branch. Returns ['plugin/case hash: pattern', ...]."""
    out = []
    for plugin, reports in sorted(reports_by_plugin.items()):
        for r in reports:
            case_id = (plugin, r['case'])
            if case_id in main_cases or case_id not in branch_checks:
                continue
            text = as_branch_prints(plugin, r['text'])
            for check in branch_checks[case_id]:
                if _fails(check, text):
                    out.append('%s/%s %s: %s' % (plugin, r['case'], hashlib.sha256(r['text'].encode()).hexdigest()[:12],
                                                 check[0][:80]))
    return out


class NewCaseGateTest(unittest.TestCase):
    """protects=a new case's saved reports pass its own graders (main has no baseline to compare against);
    fails_when=a new-case report fails a grader, or the gate stops looking at new cases."""

    def test_toy(self):
        checks = {('p', 'new'): [('^# T', '', 'contains')], ('p', 'old'): [('^# T', '', 'contains')]}
        reports = {'p': [{'case': 'new', 'text': 'no title'}, {'case': 'old', 'text': 'no title'},
                         {'case': 'new', 'text': '# T ok'}]}
        bad = new_case_failures(reports, {('p', 'old')}, checks)
        self.assertEqual(len(bad), 1)
        self.assertIn('p/new', bad[0])

    def test_real_corpus(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            if os.environ.get('CI'):
                raise
            self.skipTest('PyYAML not installed (CI installs it)')
        base = _base()
        if not base:
            if os.environ.get('CI'):
                self.fail('no origin/main to compare against')
            self.skipTest('no origin/main')
        reports, main_cases, branch = {}, set(), {}
        for plugin, corpus in corpora().items():
            with open(corpus) as fh:
                reports[plugin] = [json.loads(l) for l in fh]
            on_main = main_folder(plugin, base)
            for case in sorted({r['case'] for r in reports[plugin]}):
                for root in ('evals', 'evals-no-search'):
                    if _git('cat-file', '-e', '%s:%s/%s/%s/case.yaml' % (base, on_main, root, case)).returncode == 0:
                        main_cases.add((plugin, case))
                    path = os.path.join(ROOT, plugin, root, case, 'case.yaml')
                    if os.path.exists(path):
                        with open(path) as fh:
                            branch[(plugin, case)] = _regex_checks(fh.read())
        self.assertEqual(new_case_failures(reports, main_cases, branch), [])


if __name__ == "__main__":
    unittest.main()
