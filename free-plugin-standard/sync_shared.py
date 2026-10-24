#!/usr/bin/env python3
"""Copy shared/shared_rules.py into each free plugin and stamp the shared markdown blocks (S-062).

custody-check and build-decisions share rules: the stop-line field list and matcher, the files never
to open, and some report text. The one place to edit them is free-plugin-standard/shared/shared_rules.py.
Each plugin ships a byte-identical copy next to its scripts (COPIES), and markdown carries generated
blocks between markers (BLOCKS):

  <!-- shared:NAME -->
  ...generated text...
  <!-- /shared:NAME -->

The CI guard also fails when a plugin defines one of the shared names itself (GUARDED), outside the
registered copies and EXCLUDED paths.

  python3 free-plugin-standard/sync_shared.py           rewrite the copies and blocks
  python3 free-plugin-standard/sync_shared.py --check   exit 1 if anything is stale, hand-edited or copied

Every failure is one line on stderr: `<kind> <file>:<line> block <NAME>: <fix>`. A rewrite checks
everything first and writes nothing when any check fails. Standard library only.
"""
import argparse
import ast
import fnmatch
import os
import re
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CANONICAL = "free-plugin-standard/shared/shared_rules.py"
RUN = "run: python3 free-plugin-standard/sync_shared.py"

# ------------------------------------------------------------------ the registry (the one list)
# An entry joins in the commit that migrates it: a copy when its plugin loads it, a block when its
# markers land, a plugin's guarded names when it no longer defines them itself.

COPIES = (
    "build-decisions/skills/build-decisions/scripts/shared_rules.py",
    "custody-check/skills/custody-check/scripts/shared_rules.py",
)
BLOCKS = {
    "mistake-meanings": ("custody-check/skills/custody-check/assets/verdict-template.md",
                         "build-decisions/skills/build-decisions/SKILL.md"),
    "stopline-fields": ("build-decisions/skills/build-decisions/SKILL.md", "custody-check/skills/custody-check/SKILL.md"),
    "never-open": ("build-decisions/skills/build-decisions/SKILL.md", "build-decisions/README.md",
                   "custody-check/skills/custody-check/SKILL.md", "custody-check/README.md"),
}
GUARDED_NAMES = ("STOPLINE_FIELDS", "_stopline_norm", "stopline_terms", "stopline_line_terms", "NEVER_OPEN_DIRS",
                 "NEVER_OPEN_DIR_PAIRS", "NEVER_OPEN_FILE_RE", "NEVER_OPEN_FILES", "KEY_SENTENCE", "MISTAKE_MEANINGS",
                 "stopline_whole_terms", "NEVER_OPEN_INSTRUCTION_FILES", "NEVER_OPEN_INSTRUCTION_FOLDERS")
GUARDED = {
    "build-decisions": GUARDED_NAMES,
    "custody-check": GUARDED_NAMES,
}
EXCLUDED = (
    ("custody-check/skills/custody-check/scripts/custody_scan_0_3_2.py", "frozen 0.3.2 release, sha-pinned"),
    ("*/evals/*", "eval cases: model inputs and graders"),
    ("*/scripts/fixtures/*", "test apps that hold these names on purpose"),
    ("free-plugin-standard/corpus/*", "recorded reports"),
    ("*_test.py", "tests name the rules to check them"),
)
REGISTRY = {"copies": COPIES, "blocks": BLOCKS, "guarded": GUARDED, "excluded": EXCLUDED}

# ------------------------------------------------------------------ rendering

def _code_list(names):
    return ", ".join("`%s`" % n for n in names)


RENDER = {
    "mistake-meanings": lambda m: "\n".join('- %s: "%s"' % pair for pair in m.MISTAKE_MEANINGS),
    "stopline-fields": lambda m: _code_list(m.STOPLINE_FIELDS),
    "never-open": lambda m: "instruction files (%s, and the folders %s)" % (
        _code_list(m.NEVER_OPEN_INSTRUCTION_FILES), _code_list(m.NEVER_OPEN_INSTRUCTION_FOLDERS)),
}

START_RE = re.compile(r"^(?P<indent>[ \t]*)<!-- shared:(?P<name>[a-z0-9-]+) -->[ \t]*$")
END_RE = re.compile(r"^[ \t]*<!-- /shared:(?P<name>[a-z0-9-]+) -->[ \t]*$")
INLINE_RE = re.compile(r"<!-- shared:(?P<name>[a-z0-9-]+) -->(?P<text>.*?)<!-- /shared:(?P=name) -->")
ANY_MARKER = "<!-- shared:", "<!-- /shared:"


class Failure(Exception):
    pass


def _read_text(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _canonical_bytes(root):
    with open(os.path.join(root, CANONICAL), "rb") as fh:
        return fh.read().replace(b"\r\n", b"\n")


def _load_canonical(root):
    data = _canonical_bytes(root)
    module = types.ModuleType("shared_rules")
    module.__file__ = os.path.join(root, CANONICAL)
    try:
        exec(compile(data, module.__file__, "exec"), module.__dict__)
    except Exception as exc:
        line = getattr(exc, "lineno", None) or 1
        raise Failure("hand-edited %s:%d block shared_rules: fix the %s in this file"
                      % (CANONICAL, line, type(exc).__name__))
    return module


def render_block(root, name, module=None):
    return RENDER[name](module or _load_canonical(root))


def is_excluded(rel, excluded=EXCLUDED):
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern, _reason in excluded)


# ------------------------------------------------------------------ markdown blocks

def parse_blocks(text):
    """Return (blocks, errors). A line block is (name, start_line, end_line, indent), lines 1-based (the markers);
    an inline block, both markers on one line, is (name, line, None, (start, end)) with the text's span on the line."""
    blocks, errors, open_ = [], [], None
    for n, line in enumerate(text.split("\n"), 1):
        start, end = START_RE.match(line), END_RE.match(line)
        if start:
            if open_:
                errors.append((open_[1], open_[0]))
            open_ = (start.group("name"), n, start.group("indent"))
        elif end:
            if open_ and open_[0] == end.group("name"):
                blocks.append((open_[0], open_[1], n, open_[2]))
            else:
                if open_:
                    errors.append((open_[1], open_[0]))
                errors.append((n, end.group("name")))
            open_ = None
        elif any(m in line for m in ANY_MARKER):
            for m in INLINE_RE.finditer(line):
                blocks.append((m.group("name"), n, None, m.span("text")))
            rest = INLINE_RE.sub("", line)
            if any(m in rest for m in ANY_MARKER):
                errors.append((n, re.search(r"shared:([a-z0-9-]*)", rest).group(1)))
    if open_:
        errors.append((open_[1], open_[0]))
    return blocks, errors


def _dedent(lines):
    body = [ln for ln in lines if ln.strip()]
    if not body:
        return lines
    prefix = os.path.commonprefix([re.match(r"[ \t]*", ln).group() for ln in body])
    return [ln[len(prefix):] if ln.strip() else "" for ln in lines]


def _targets(reg):
    """Each target file once, in registry order, with the block names registered for it."""
    out = {}
    for name, files in reg["blocks"].items():
        for rel in files:
            out.setdefault(rel, []).append(name)
    return out


def _blocks_plan(root, reg, module):
    """Check every registered block. Return (errors, stale, new_texts): stale are hand-edited lines,
    new_texts maps a file to its rewritten text when it changes."""
    errors, stale, new_texts = [], [], {}
    for rel, names in _targets(reg).items():
        path = os.path.join(root, rel)
        try:
            raw = _read_text(path)
        except OSError:
            for name in names:
                errors.append("missing-marker %s:1 block %s: add <!-- shared:%s -->…<!-- /shared:%s --> in %s"
                              % (rel, name, name, name, rel))
            continue
        text = raw.replace("\r\n", "\n")
        blocks, bad = parse_blocks(text)
        for line, name in bad:
            if name in names:
                fix = "give each <!-- shared:%s --> one <!-- /shared:%s --> after it in %s" % (name, name, rel)
            else:
                fix = "register %s for %s in BLOCKS in free-plugin-standard/sync_shared.py, or delete its markers" % (name, rel)
            errors.append("unbalanced-marker %s:%d block %s: %s" % (rel, line, name, fix))
        for name, start, _end, _span in blocks:
            if name not in names:
                errors.append("unbalanced-marker %s:%d block %s: register %s for %s in BLOCKS in "
                              "free-plugin-standard/sync_shared.py, or delete its markers" % (rel, start, name, name, rel))
        found = {b[0] for b in blocks} | {name for _line, name in bad}
        for name in names:
            if name not in found:
                errors.append("missing-marker %s:1 block %s: add <!-- shared:%s -->…<!-- /shared:%s --> in %s"
                              % (rel, name, name, name, rel))
        lines = text.split("\n")
        # inline blocks first, right to left on each line, so spans stay valid
        for name, line_no, _none, span in sorted((b for b in blocks if b[2] is None), key=lambda b: (b[1], -b[3][0])):
            if name not in names:
                continue
            want = render_block(root, name, module)
            line = lines[line_no - 1]
            if line[span[0]:span[1]] != want:
                stale.append("hand-edited %s:%d block %s: %s (edit %s, not this block)" % (rel, line_no, name, RUN, CANONICAL))
                lines[line_no - 1] = line[:span[0]] + want + line[span[1]:]
        out, pos = [], 0
        for name, start, end, indent in (b for b in blocks if b[2] is not None):
            if name not in names:
                continue
            want = render_block(root, name, module).split("\n")
            have = lines[start:end - 1]
            if _dedent(have) != want:
                stale.append("hand-edited %s:%d block %s: %s (edit %s, not this block)" % (rel, start, name, RUN, CANONICAL))
            out.extend(lines[pos:start])
            out.extend(indent + ln if ln else "" for ln in want)
            pos = end - 1
        out.extend(lines[pos:])
        new = "\n".join(out)
        if new != raw:
            new_texts[rel] = new
    return errors, stale, new_texts


# ------------------------------------------------------------------ copies

def _copies_plan(root, reg):
    canon = _canonical_bytes(root)
    stale = []
    for rel in reg["copies"]:
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                same = fh.read() == canon
        except OSError:
            same = False
        if not same:
            stale.append(rel)
    return stale, canon


# ------------------------------------------------------------------ the guard

def hand_copies(root, reg):
    """A top-level definition of a guarded name in a guarded plugin's .py files, outside copies and EXCLUDED."""
    errors = []
    fix = "delete the copy and use shared_rules, or add the path to EXCLUDED with a reason"
    for plugin, names in reg["guarded"].items():
        for d, dirs, files in os.walk(os.path.join(root, plugin)):
            dirs[:] = sorted(x for x in dirs if x not in (".git", "__pycache__", "node_modules"))
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                rel = os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/")
                if rel in reg["copies"] or is_excluded(rel, reg["excluded"]):
                    continue
                try:
                    tree = ast.parse(_read_text(os.path.join(d, f)))
                except (SyntaxError, ValueError, OSError) as exc:
                    errors.append("hand-copy %s:%d block (unread): fix the file so the guard can read it"
                                  % (rel, getattr(exc, "lineno", None) or 1))
                    continue
                for node in tree.body:
                    for name in _defined(node):
                        if name in names:
                            errors.append("hand-copy %s:%d block %s: %s" % (rel, node.lineno, name, fix))
    return errors


def _defined(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
    out = []
    for t in targets:
        out.extend(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
    return out


# ------------------------------------------------------------------ check and rewrite

def check(root=ROOT, reg=REGISTRY):
    try:
        module = _load_canonical(root)
    except Failure as f:
        return [str(f)]
    stale_copies, _ = _copies_plan(root, reg)
    errors = ["stale-copy %s:1 block shared_rules: %s" % (rel, RUN) for rel in stale_copies]
    block_errors, stale_blocks, _ = _blocks_plan(root, reg, module)
    return errors + block_errors + stale_blocks + hand_copies(root, reg)


def _write_atomic(path, data):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o644
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".sync-shared-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def rewrite(root=ROOT, reg=REGISTRY):
    """Return (errors, written). Writes nothing when there is any error."""
    try:
        module = _load_canonical(root)
    except Failure as f:
        return [str(f)], []
    stale_copies, canon = _copies_plan(root, reg)
    block_errors, _stale, new_texts = _blocks_plan(root, reg, module)
    errors = block_errors + hand_copies(root, reg)
    if errors:
        return errors, []
    written = []
    for rel in stale_copies:
        _write_atomic(os.path.join(root, rel), canon)
        written.append(rel)
    for rel, text in new_texts.items():
        _write_atomic(os.path.join(root, rel), text.encode("utf-8"))
        written.append(rel)
    return [], written


def main(argv=None, root=ROOT, reg=REGISTRY):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="report only; exit 1 on any problem")
    args = parser.parse_args(argv)
    if args.check:
        errors = check(root, reg)
        for e in errors:
            sys.stderr.write(e + "\n")
        return 1 if errors else 0
    errors, written = rewrite(root, reg)
    for e in errors:
        sys.stderr.write(e + "\n")
    if errors:
        sys.stderr.write("side effects: none\n")
        return 1
    for rel in written:
        sys.stdout.write("wrote %s\n" % rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
