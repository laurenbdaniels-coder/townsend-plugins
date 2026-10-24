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

_BLOCK = r"/\*[\s\S]*?\*/"
_DQ_LINE = r'"(?:[^"\\\n]|\\.)*"'
_SQ_LINE = r"'(?:[^'\\\n]|\\.)*'"
# Each kind: one pattern; named groups say what to blank (drop) and what to keep as written (keep).
_STRIP = {
    # SQL: -- and /* */ comments; '...' values (may span lines, '' is a quote inside) are dropped;
    # "..." and `...` are quoted identifiers and stay.
    "sql": re.compile(r"(?P<drop>--[^\n]*|%s|'[^']*(?:''[^']*)*')|(?P<keep>\"[^\"\n]*\"|`[^`\n]*`)" % _BLOCK),
    # Prisma, TS/JS: //, ///, /* */, and a line that starts with * or <!--; '...' and "..." values are
    # dropped, except a Prisma @map("...") / @@map("...") argument; `...` stays.
    "slash": re.compile(r"(?P<drop>//[^\n]*|%s|(?m:^[ \t]*(?:\*|<!--)[^\n]*))|(?P<str>%s|%s)|(?P<keep>`[^`]*`)"
                        % (_BLOCK, _DQ_LINE, _SQ_LINE)),
    # Python, Ruby: # comments; '...' and "..." values.
    "hash": re.compile(r"(?P<drop>#[^\n]*|%s|%s)" % (_DQ_LINE, _SQ_LINE)),
    # GraphQL: # comments; """...""" and "..." descriptions.
    "graphql": re.compile(r'(?P<drop>#[^\n]*|"""[\s\S]*?"""|%s)' % _DQ_LINE),
}
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
    An unclosed quote or comment is left as written, so it never hides the rest of the file."""
    if kind not in _STRIP:
        raise ValueError("unknown kind: %r" % (kind,))
    out = []
    pos = 0
    for m in _STRIP[kind].finditer(text):
        if m.lastgroup == "keep":
            continue
        if m.lastgroup == "str" and _MAP_ARG.search(text, max(0, m.start() - 16), m.start()):
            continue
        out.append(text[pos:m.start()])
        out.append(_NOT_NEWLINE.sub(" ", m.group()))
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def stopline_line_terms(text, kind, clip=None):
    """Yield (line_no, identifier, term) for every stop-line term in a whole file's text, lazily.

    Comments and string values never count (strip_for_stopline). clip keeps only the first clip
    characters of each line. The identifier is the app's own text: callers show the term, not it.
    """
    stripped = strip_for_stopline(text, kind)
    for line_no, line in enumerate(stripped.split("\n"), 1):
        if clip is not None:
            line = line[:clip]
        if not _FLAT_ANY.search(line.lower().replace("_", "")):
            continue
        for identifier in IDENT_RE.findall(line):
            for term in stopline_terms(identifier):
                yield line_no, identifier, term
