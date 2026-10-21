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


def make_repo(cases, exempt=None, words=None):
    """A throwaway repo root holding the real pack and one fake free plugin, 'demo-plugin'."""
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, 'free-plugin-standard'))
    pack = json.load(open(os.path.join(HERE, 'pack.json')))
    pack['plugins'] = {'demo-plugin': {'exempt': exempt or {}}}
    if words is not None:
        pack['plugins']['demo-plugin']['words'] = words
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

    def repo(self, cases, exempt=None, words=None):
        root = make_repo(cases, exempt, words)
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
        self.assertEqual(self._graders(root)['std-out-of-sync']['pattern'], 'If they get out of sync:')

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
    'build-decisions': (
        (r"Not checked: [^\n]*This version also does not check payments, screens that write prices or paid status, "
         r"sign-in checks on server code, or library versions\.[^\n]*Not found does not mean",
         r"Not checked: [^\n]*This version also does not check sign-in checks on server code, or library versions\. "
         r"Payment places are found from the files, not tested in the app\.[^\n]*Not found does not mean",
         '0.5.0 checks payments, so the fixed Not checked line stops naming them (S-008).'),
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
ALLOWED = {
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
NEW_GRADERS = {}
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
        self.assertEqual(seen, 8)


if __name__ == '__main__':
    unittest.main()
