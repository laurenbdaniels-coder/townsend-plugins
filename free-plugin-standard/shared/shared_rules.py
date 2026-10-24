"""Rules custody-check and build-decisions share (S-062). Standard library only, Python 3.9.

This is the one file to edit. Each plugin ships a byte-identical copy next to its scripts:
  custody-check/skills/custody-check/scripts/shared_rules.py
  build-decisions/skills/build-decisions/scripts/shared_rules.py
After an edit, run: python3 free-plugin-standard/sync_shared.py
Each script loads its copy by path (scripts run as python3 -I, so the folder is not on sys.path).

No type annotations: Python 3.8 must still reach each script's own python-too-old check.
"""
import os
import re

# ------------------------------------------------------------------ stop-line field names

# Fixed order: custody-check's twelve, then birth_date and birthday. Anything needing a set derives it.
STOPLINE_FIELDS = ("ssn", "social_security", "dob", "date_of_birth", "birthdate", "medical", "diagnosis",
                   "credit_card", "card_number", "cc_number", "iban", "passport", "birth_date", "birthday")

RUN_TOGETHER_MIN = 6  # letters; shorter terms (ssn, dob, iban) match whole words only

_WHOLE = tuple((t, re.compile(r"(?:^|_)%s(?:_|$)" % t)) for t in STOPLINE_FIELDS)
_FLAT = tuple((t, t.replace("_", "")) for t in STOPLINE_FIELDS)
# Every hit, whole or run-together, holds a term's letters with underscores removed: a cheap first test.
_FLAT_ANY = re.compile("|".join(sorted({f for _t, f in _FLAT}, key=len, reverse=True)))
_CAMEL_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def _stopline_norm(identifier):
    """dateOfBirth -> date_of_birth, userSSN -> user_ssn."""
    s = _CAMEL_1.sub(r"\1_\2", identifier)
    s = _CAMEL_2.sub(r"\1_\2", s)
    return _NON_WORD.sub("_", s.lower())


def stopline_whole_terms(identifier):
    """Step (a) of stopline_terms alone: the terms that are whole words of the identifier's snake form."""
    n = _stopline_norm(identifier)
    if not _FLAT_ANY.search(n.replace("_", "")):
        return []
    return [t for t, rx in _WHOLE if rx.search(n)]


def stopline_terms(identifier):
    """The stop-line terms one identifier (a field or column name, never a line) names, in list order.

    (a) every term that is a whole word of the snake form (a term may span words: birth_date);
    (b) only when (a) finds none: the single longest term of 6+ letters run together (creditcard),
        ties to the earlier term in the list.
    Returns list members only, never the app's own text.
    """
    hits = stopline_whole_terms(identifier)
    if hits:
        return hits
    flat = _stopline_norm(identifier).replace("_", "")
    best = None
    for t, f in _FLAT:
        if len(f) >= RUN_TOGETHER_MIN and f in flat and (best is None or len(f) > len(best[1])):
            best = (t, f)
    return [best[0]] if best else []


# ------------------------------------------------------------------ files never to open

# Equal to custody-check 0.3.2's (shared_rules_test checks). AI-tool instruction files and folders.
NEVER_OPEN_DIRS = frozenset({".claude", ".codex", ".agents", ".windsurf", ".clinerules", ".gemini", ".kiro", ".roo",
                             ".trae", ".augment", ".amazonq", ".junie", ".continue", ".aider", ".opencode"})
NEVER_OPEN_DIR_PAIRS = frozenset({(".cursor", "rules"), (".github", "instructions"), (".github", "prompts"),
                                  (".github", "agents")})
NEVER_OPEN_FILE_RE = re.compile(r"^(?:claude|agents?|gemini|conventions|copilot-instructions)(?:[.-][^/]*)?\.md$|^\.aider.*$|.*\.prompt\.md$|.*\.agent\.md$|.*\.instructions\.md$|.*\.mdc$", re.I)
NEVER_OPEN_FILES = frozenset({".cursorrules", ".windsurfrules", ".clinerules", ".rules", "opencode.json", ".roomodes"})

# The same list as prose (the never-open markdown block): instruction files, then folders.
NEVER_OPEN_INSTRUCTION_FILES = ("CLAUDE.md", "AGENTS.md", "AGENT.md", "GEMINI.md", "CONVENTIONS.md",
                                "copilot-instructions.md", "*.prompt.md", "*.agent.md", "*.instructions.md", "*.mdc",
                                ".cursorrules", ".windsurfrules", ".clinerules", ".rules", ".roomodes", "opencode.json",
                                ".aider*")
NEVER_OPEN_INSTRUCTION_FOLDERS = (".claude/", ".codex/", ".agents/", ".cursor/rules/", ".github/instructions/",
                                  ".github/prompts/", ".github/agents/", ".windsurf/", ".clinerules/", ".gemini/", ".kiro/", ".roo/",
                                  ".trae/", ".augment/", ".amazonq/", ".junie/", ".continue/", ".aider/", ".opencode/")

# ------------------------------------------------------------------ report text (stamped into markdown)

# The one safety step both plugins keep (SCOPE.md: "replace it now"). Lowercase, no full stop: each rule uses it
# mid-sentence after "say in one line:" or "answer with one line:". sync_shared.py stamps it as the key-clause block.
KEY_SENTENCE = "assume it is exposed, and replace it now with a new one"

# "What a mistake costs": label, then the sentence the report copies. sync_shared.py renders these as
# `- <label>: "<sentence>"` lines between <!-- shared:mistake-meanings --> markers.
MISTAKE_MEANINGS = (
    ("card details the app handles itself",
     "If they leak, your customers' cards are exposed, and card industry rules apply to you."),
    ("money held or moved for other people",
     "A mistake here loses other people's money, and money rules apply to you."),
    ("health data, or other people's sensitive data (fields such as ID numbers, dates of birth, passports)",
     "If this data leaks, the people it belongs to can be harmed, and laws on this data can apply to you."),
    ("real scale, or a contract that needs the app to stay up",
     "A mistake here reaches many people at once, or breaks your contract."),
    ("money, and it is not clear which kind",
     "Your app handles money, and it is not clear whether it holds card details or other people's money."),
)

# ------------------------------------------------------------------ whole files

_SQL_EXTS = (".sql", ".psql", ".pgsql", ".ddl")
KINDS = ("sql", "slash", "hash", "graphql")
IDENT_RE = re.compile(r"[A-Za-z0-9_]+")

# Each kind: the openers it knows. strip_for_stopline finds each closer with str.find, one pass forward.
_OPENERS = {
    # SQL: -- and /* */ comments; '...' values (may span lines, '' is a quote inside) are dropped;
    # "..." and `...` are quoted identifiers and stay.
    "sql": re.compile(r"(?P<line>--)|(?P<block>/\*)|(?P<sqlstr>')|(?P<keep>[\"`])"),
    # Prisma, TS/JS: //, ///, /* */, and a line that starts with * or <!--; '...' and "..." values are
    # dropped, except a Prisma @map("...") / @@map("...") argument; `...` stays.
    "slash": re.compile(r"(?P<line>//|(?m:^[ \t]*(?:\*|<!--)))|(?P<block>/\*)|(?P<str>[\"'])|(?P<tick>`)"),
    # Python, Ruby: # comments; '...' and "..." values.
    "hash": re.compile(r"(?P<line>#)|(?P<str>[\"'])"),
    # GraphQL: # comments; """...""" and "..." descriptions.
    "graphql": re.compile(r'(?P<line>#)|(?P<triple>""")|(?P<str>")'),
}
_LINE_STRING = {'"': re.compile(r'"(?:[^"\\\n]|\\.)*"'), "'": re.compile(r"'(?:[^'\\\n]|\\.)*'")}
_MAP_ARG = re.compile(r"@map\(\s*$")
_NOT_NEWLINE = re.compile(r"[^\n]")


def stopline_kind(name):
    """The comment rules for a file, by its name: sql, hash (.py, .rb), graphql, or slash (everything else)."""
    ext = os.path.splitext(name)[1].lower()
    if ext in _SQL_EXTS:
        return "sql"
    if ext in (".py", ".rb"):
        return "hash"
    if ext in (".graphql", ".gql"):
        return "graphql"
    return "slash"


def strip_for_stopline(text, kind):
    """Blank comments and string values with spaces. Length and newlines stay, so line numbers hold.
    An unclosed quote or comment is left as written, so it never hides the rest of the file. One pass
    forward: each closer is found once, and an opener with no closer after it marks every later one."""
    if kind not in _OPENERS:
        raise ValueError("unknown kind: %r" % (kind,))
    opener = _OPENERS[kind]
    n = len(text)
    out = []
    pos = done = 0  # pos: where the next opener search starts; done: text up to here is already in out
    none_after = {}  # closer -> a position after which that closer never occurs
    eol_at = [-1, -1]  # [line start searched from, its end]

    def eol(i):
        if not (eol_at[0] <= i <= eol_at[1]):
            j = text.find("\n", i)
            eol_at[0], eol_at[1] = i, (n if j < 0 else j)
        return eol_at[1]

    def find(closer, i, stop=None):
        if closer in none_after and i >= none_after[closer]:
            return -1
        j = text.find(closer, i, n if stop is None else stop)
        if j < 0 and stop is None:
            none_after[closer] = i
        return j

    while True:
        m = opener.search(text, pos)
        if m is None:
            break
        kind_of, start = m.lastgroup, m.start()
        drop_end = None
        if kind_of == "line":
            drop_end = eol(start)
        elif kind_of == "block":
            j = find("*/", m.end())
            drop_end = None if j < 0 else j + 2
        elif kind_of == "triple":
            j = find('"""', m.end())
            drop_end = None if j < 0 else j + 3
        elif kind_of == "sqlstr":
            i = m.end()
            j = find("'", i)
            while j >= 0 and j + 1 < n and text[j + 1] == "'":  # '' is a quote inside the value
                j = find("'", j + 2)
            drop_end = None if j < 0 else j + 1
        elif kind_of == "str":
            sm = _LINE_STRING[m.group()].match(text, start, eol(start))
            if sm and not (kind == "slash" and m.group() == '"' and _MAP_ARG.search(text, max(0, start - 16), start)):
                drop_end = sm.end()
            elif sm:  # a Prisma @map("...") argument is an identifier: keep it
                pos = sm.end()
                continue
        elif kind_of == "keep":  # an SQL quoted identifier, kept as written
            j = find(m.group(), m.end(), eol(start))
            pos = m.end() if j < 0 else j + 1
            continue
        elif kind_of == "tick":  # a JS template literal, kept as written (it may span lines)
            j = find("`", m.end())
            pos = m.end() if j < 0 else j + 1
            continue
        if drop_end is None:  # unclosed: leave the opener as written
            pos = m.end()
            continue
        out.append(text[done:start])
        out.append(_NOT_NEWLINE.sub(" ", text[start:drop_end]))
        pos = done = drop_end
    out.append(text[done:])
    return "".join(out)


def stopline_line_terms(text, kind, clip=None):
    """Yield (line_no, identifier, term) for every stop-line term in a whole file's text, lazily.

    Comments and string values never count (strip_for_stopline). clip keeps only the first clip
    characters of each line. The identifier is the app's own text: callers show the term, not it.
    """
    if kind not in _OPENERS:
        raise ValueError("unknown kind: %r" % (kind,))
    # A hit's letters (underscores removed) sit in the whole file's: no term's letters anywhere, no hit.
    if not _FLAT_ANY.search(text.lower().replace("_", "")):
        return
    stripped = strip_for_stopline(text, kind)
    for line_no, line in enumerate(stripped.split("\n"), 1):
        if clip is not None:
            line = line[:clip]
        if not _FLAT_ANY.search(line.lower().replace("_", "")):
            continue
        for identifier in IDENT_RE.findall(line):
            for term in stopline_terms(identifier):
                yield line_no, identifier, term
