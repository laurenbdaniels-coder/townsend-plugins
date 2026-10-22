#!/usr/bin/env python3
"""Stamp the free-plugin standard's shared graders into every free plugin's eval cases.

`claude plugin eval` has no include for case.yaml, so each case carries a generated copy of the
pack between two marker lines at the end of its `graders:` list:

  # >>> free-plugin-standard: always issues
  ...generated graders...
  # <<< free-plugin-standard

Groups come from pack.json: `always` for every case that renders a report, `issues` when the case
expects at least one issue. Every case of a plugin listed in pack.json carries a block or is
exempt there with a reason. A plugin may give its own words (`words`) only for the graders listed
in `plugin_words`: the per-issue risk line as a plain label ending in a colon, the count line as one
bold line that starts with a word. A plugin may leave out (`omit`, with a reason) only a grader
listed in `omittable`; the no-fix line (no fix prompt, no code words) is never on that list.

  python3 free-plugin-standard/sync_graders.py           rewrite the blocks from pack.json
  python3 free-plugin-standard/sync_graders.py --check   exit 1 if any block is missing or stale

Standard library only.
"""
import argparse
import glob
import json
import os
import re
import sys

START = re.compile(r'^  # >>> free-plugin-standard:(?P<groups>[^\n]*)\n', re.M)
END = '  # <<< free-plugin-standard\n'
KEYS = ('name', 'type', 'pattern', 'flags', 'match')
REQUIRED_GROUP = 'always'
LABEL = re.compile(r"[A-Z][A-Za-z' ]{0,58}:")
# A count line is one bold line: the pack's own start and end, and a literal capitalised word first,
# so a plugin can change its words but not turn the line into a pattern that matches anything.
BOLD_START = r'(?:^|\n)\*\*'
BOLD_END = r'\.\*\*[ \t]*(?=\n|$)'
BOLD_WORD = re.compile(r'[A-Z][a-z]+ ')


def _label(value):
    return isinstance(value, str) and LABEL.fullmatch(value) is not None


def _bold_line(value):
    if not isinstance(value, str) or not value.startswith(BOLD_START) or not value.endswith(BOLD_END):
        return False
    if not BOLD_WORD.match(value[len(BOLD_START):]):
        return False
    try:
        compiled = re.compile(value)
    except re.error:
        return False
    # a top-level `|` (or any other trick) that lets it match a plain line or nothing would match any report
    return not compiled.search("\nplain text\n") and not compiled.search("")


# Each grader a plugin may reword, and the shape its words must have.
SHAPES = {
    'std-out-of-sync': (_label, 'a plain label ending in a colon'),
    'std-count-line': (_bold_line, 'one bold line that starts with a capitalised word and ends with a full stop'),
}


def load_pack(root):
    with open(os.path.join(root, 'free-plugin-standard', 'pack.json')) as fh:
        return json.load(fh)


def render(groups, pack, plugin=None):
    conf = pack['plugins'].get(plugin, {}) if plugin else {}
    words, omit = conf.get('words', {}), conf.get('omit', {})
    lines = []
    for group in groups:
        for grader in pack['groups'][group]:
            if grader['name'] in omit:
                continue
            grader = dict(grader, pattern=words.get(grader['name'], grader['pattern']))
            lines.append('  - name: %s\n' % json.dumps(grader['name']))
            for key in KEYS[1:]:
                lines.append('    %s: %s\n' % (key, json.dumps(grader[key], ensure_ascii=False)))
    return ''.join(lines)


def words_problems(plugin, conf, pack):
    allowed = set(pack.get('plugin_words', []))
    for name, label in sorted(conf.get('words', {}).items()):
        if name not in allowed:
            yield '%s: words for %s, which plugins may not reword (only %s)' % (
                plugin, name, ', '.join(sorted(allowed)) or 'none')
        elif name not in SHAPES:
            yield '%s: words for %s, which has no shape rule in sync_graders.py' % (plugin, name)
        elif not SHAPES[name][0](label):
            yield '%s: words for %s must be %s, got %r' % (plugin, name, SHAPES[name][1], label)
    omittable = set(pack.get('omittable', []))
    for name, reason in sorted(conf.get('omit', {}).items()):
        if name not in omittable:
            yield '%s: omit %s, which plugins may not leave out (only %s)' % (
                plugin, name, ', '.join(sorted(omittable)) or 'none')
        elif not isinstance(reason, str) or not reason.strip():
            yield '%s: omit %s needs a reason' % (plugin, name)


def case_files(root, plugin):
    # evals/ holds the usual cases; evals-<name>/ folders hold cases run on their own (e.g. evals-no-search).
    return sorted(glob.glob(os.path.join(root, plugin, 'evals', '*', 'case.yaml')) +
                  glob.glob(os.path.join(root, plugin, 'evals-*', '*', 'case.yaml')))


def _parse(text, pack):
    """Return (groups, start, body_start, body_end, end) for the one block, or an error string."""
    starts = list(START.finditer(text))
    if not starts:
        return None
    if len(starts) > 1 or text.count(END) != 1:
        return 'has more than one free-plugin-standard block, or a block without its end line'
    m = starts[0]
    end_at = text.find(END, m.end())
    if end_at < 0:
        return 'block has no end line'
    if text[end_at + len(END):].strip():
        return 'block must end the file (it closes the graders: list)'
    groups = m.group('groups').split()
    unknown = [g for g in groups if g not in pack['groups']]
    if unknown:
        return 'unknown group(s): %s' % ' '.join(unknown)
    if REQUIRED_GROUP not in groups:
        return "block must carry the '%s' group" % REQUIRED_GROUP
    if len(set(groups)) != len(groups):
        return 'block repeats a group'
    return groups, m.start(), m.end(), end_at


def _scan(root):
    """Yield (path, problem or None, new_text or None) for every case of every registered plugin."""
    pack = load_pack(root)
    for path in sorted(glob.glob(os.path.join(root, '*', 'evals', '*', 'case.yaml')) +
                       glob.glob(os.path.join(root, '*', 'evals-*', '*', 'case.yaml'))):
        plugin = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
        if plugin not in pack['plugins'] and START.search(open(path, encoding='utf-8').read()):
            yield path, 'carries a free-plugin-standard block but %s is not registered in pack.json' % plugin, None
    for plugin, conf in sorted(pack['plugins'].items()):
        exempt = conf.get('exempt', {})
        bad_words = list(words_problems(plugin, conf, pack))
        for problem in bad_words:
            yield plugin, problem, None
        if bad_words:
            continue
        names = set()
        if not case_files(root, plugin):
            yield plugin, 'registered in pack.json but has no eval cases', None
        for path in case_files(root, plugin):
            name = os.path.basename(os.path.dirname(path))
            names.add(name)
            text = open(path, encoding='utf-8').read()
            parsed = _parse(text, pack)
            if name in exempt:
                if not str(exempt[name]).strip():
                    yield path, 'exempt without a reason in pack.json', None
                elif parsed is not None:
                    yield path, 'exempt in pack.json but carries a block; drop one', None
                continue
            if parsed is None:
                yield path, 'no free-plugin-standard block and not exempt in pack.json', None
                continue
            if isinstance(parsed, str):
                yield path, parsed, None
                continue
            groups, _, body_start, body_end = parsed
            want = render(groups, pack, plugin)
            if text[body_start:body_end] != want:
                yield path, 'stale block: run python3 free-plugin-standard/sync_graders.py', \
                    text[:body_start] + want + text[body_end:]
        for name in sorted(set(exempt) - names):
            yield os.path.join(plugin, 'evals', name), 'exempt in pack.json but the case does not exist', None


def check(root):
    return ['%s: %s' % (path, problem) for path, problem, _ in _scan(root)]


def sync(root):
    """Rewrite stale blocks. Returns the paths changed. Problems sync cannot fix are left for check."""
    changed = []
    for path, _, new_text in list(_scan(root)):
        if new_text is not None:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(new_text)
            changed.append(path)
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='report problems, change nothing')
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args(argv)
    if not args.check:
        for path in sync(args.root):
            print('updated %s' % os.path.relpath(path, args.root))
    errors = check(args.root)
    for e in errors:
        print(e)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
