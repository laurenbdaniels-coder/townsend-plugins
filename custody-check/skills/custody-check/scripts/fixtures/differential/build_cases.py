"""Build cases.json for NeverWorseThanMainTests: realistic files plus every repro from review, with the answers
the released scanner gives on them (Q1, Q3, Q9, partial, Q10 PII fields).

Usage (from the repo, after each release; the ref is a commit on main, e.g. origin/main or a merge sha):
       python3 build_cases.py <release-ref> cases.json

The release's whole scripts/ folder is exported with git archive: since 0.3.3 custody_scan.py loads
custody_scan_0_3_2.py from its own folder, so one copied file only ever answers internal:release-missing.
Add a case for every input a review finds; never edit cases.json by hand."""
import io, json, os, shutil, subprocess, sys, tarfile, tempfile

SCRIPTS = "custody-check/skills/custody-check/scripts"


def extract_scripts(tar_bytes, dest):
    """Write the regular files under SCRIPTS/ from a tar into dest. Links, devices, absolute names and any
    name with a .. part are skipped, so no member can write outside dest."""
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
        for m in tf.getmembers():
            rel = m.name[len(SCRIPTS) + 1:] if m.name.startswith(SCRIPTS + "/") else ""
            parts = rel.split("/")
            if not m.isfile() or not rel or ".." in parts or "" in parts or os.path.isabs(rel) or "\\" in rel:
                continue
            out = os.path.join(dest, *parts)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(tf.extractfile(m).read())


def export_release(ref, dest, repo_root):
    """Write the scripts folder as it is at ref into dest (git archive; regular files only, every name checked to
    stay under dest). Returns (path of its custody_scan.py, full commit sha). Raises CalledProcessError on a bad ref."""
    git = lambda *a: subprocess.run(("git",) + a, cwd=repo_root, capture_output=True, check=True, timeout=120).stdout
    sha = git("rev-parse", "--verify", "--quiet", ref + "^{commit}").decode().strip()
    extract_scripts(git("archive", "--format=tar", sha, SCRIPTS), dest)
    return os.path.join(dest, "custody_scan.py"), sha


A = "src/components/A.tsx"
BASE = {A: "export const A = () => null;\n"}
RLS = "create table public.notes (id int);\nalter table public.notes enable row level security;\n"
FB = "service cloud.firestore {\n  match /databases/{db}/documents {\n    match /{doc=**} {\n      allow read, write: %s\n    }\n  }\n}\n"
KEY = "{KEY}"  # filled in at run time: no key-shaped literal is stored in the repo
PEM = "{PEM}"
LIVE = "{LIVE}"  # a live Stripe-shaped key, filled in at run time like {KEY}
REAL = {"{KEY}": "sk-" + "proj-" + "a1b2c3d4e5f6g7h8i9j0" * 2,
        "{LIVE}": "sk_" + "live_" + "a1b2c3d4e5f6g7h8i9j0",
        "{PEM}": "-----BEGIN " + "PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\\n-----END " + "PRIVATE KEY-----\\n",
        "{PEM_BODY}": "-----BEGIN " + "PRIVATE KEY-----\n" + "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7" * 3 + "\n-----END " + "PRIVATE KEY-----\n"}  # a body 0.3.2 does not read as filler

cases = []
def case(name, files, base=True, args=None, links=None):
    """files: {rel: text} or {rel: {"repeat": text, "times": n}} (generated at run time, so cases.json stays small);
    args: scan() keyword arguments, also passed to the baseline as CLI flags; links: {new rel: existing rel} hard links."""
    c = {"name": name, "files": dict(BASE, **files) if base else dict(files)}
    if args:
        c["args"] = dict(args)
    if links:
        c["links"] = dict(links)
    cases.append(c)


def materialize(root, c):
    """Write a case's files under root, the same way NeverWorseThanMainTests._scan does."""
    for rel, body in c["files"].items():
        if isinstance(body, dict):
            body = body["repeat"] * body["times"]
        for k, v in REAL.items():
            body = body.replace(k, v)
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
    for new, old in c.get("links", {}).items():
        p = os.path.join(root, new)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        os.link(os.path.join(root, old), p)

# ---- realistic, ordinary shapes (must stay exactly as main, or better)
case("supabase init migration", {"supabase/migrations/20240101000000_init.sql": RLS + "create policy \"own rows\" on public.notes for select using (auth.uid() = owner);\n"})
case("pg_dump quoted", {"db/schema.sql": 'CREATE TABLE "public"."notes" (id int);\nALTER TABLE "public"."notes" ENABLE ROW LEVEL SECURITY;\nCREATE POLICY "p" ON "public"."notes" FOR SELECT USING ((auth.uid() = owner));\n'})
case("pg_dump open policy", {"db/schema.sql": 'CREATE TABLE "public"."notes" (id int);\nALTER TABLE "public"."notes" ENABLE ROW LEVEL SECURITY;\nCREATE POLICY "p" ON "public"."notes" USING (true);\n'})
case("table without rls", {"db/1.sql": "create table public.notes (id int);\n"})
case("rls disabled", {"db/1.sql": RLS + "alter table public.notes disable row level security;\n"})
case("using true for all", {"db/1.sql": RLS + "create policy p on public.notes for all using (true);\n"})
case("using true select only", {"db/1.sql": RLS + "create policy p on public.notes for select using (true);\n"})
case("do block enables", {"db/1.sql": "create table public.notes (id int);\ndo $$ begin alter table public.notes enable row level security; end $$;\n"})
case("do block disables", {"db/1.sql": RLS + "do $$ begin alter table public.notes disable row level security; end $$;\n"})
case("function then real disable", {"db/1.sql": RLS + "create or replace function public.touch() returns trigger language plpgsql as $$ begin new.updated_at = now(); return new; end; $$;\nalter table public.notes disable row level security;\n"})
case("seed only", {"supabase/seed.sql": "insert into notes values (1);\n"})
case("comment mentions rls", {"db/1.sql": RLS + "-- remember: never disable row level security\n"})
case("block comment mentions rls", {"db/1.sql": RLS + "/* do not: alter table public.notes disable row level security; */\n"})
case("glob in block comment", {"db/1.sql": "create table public.notes (id int);\n/* files under avatars/* are public */\n/* todo: alter table public.notes enable row level security; */\n"})
case("glob then commented disable", {"db/1.sql": RLS + "/* files under avatars/* are public */\n/* never: alter table public.notes disable row level security */\n"})
case("nested comment with quote", {"db/1.sql": RLS + '/* old /* inner */ 27" monitor */\nalter table public.notes disable row level security;\n-- 27" again\n'})
case("nested comment with apostrophe", {"db/1.sql": RLS + "/* /* x */ we don't need this */\ncreate policy p on public.notes for all using (true);\n"})
case("dash dash in string then disable", {"db/1.sql": RLS + "insert into public.log(msg) values ('a -- b');\nalter table public.notes disable row level security;\nselect 'x';\n"})
case("do then function then disable", {"db/1.sql": "create table public.notes (id int);\ndo $$ begin perform 1; end $$;\nalter table public.notes disable row level security;\ncreate or replace function public.t() returns trigger language plpgsql as $$ begin return new; end; $$;\n"})
case("do language disables", {"db/1.sql": RLS + "do language plpgsql $$ begin alter table public.notes disable row level security; end $$;\n"})
case("string mentions enable", {"db/1.sql": "create table public.notes (id int);\ncomment on table public.notes is 'alter table public.notes enable row level security';\n"})
case("string mentions using true", {"db/1.sql": RLS + "comment on table public.notes is 'using (true) is unsafe';\n"})
case("index named disable", {"db/1.sql": RLS + 'create index "disable row level security" on public.notes(id);\n'})
case("index named enable", {"db/1.sql": 'create table public.notes (id int);\ncreate index "alter table public.notes enable row level security" on public.notes(id);\n'})
case("drop and recreate", {"db/1.sql": RLS, "db/2.sql": "drop table public.notes;\ncreate table public.notes (id int);\n"})
case("rerunnable schema", {"db/schema.sql": "drop table if exists public.notes;\n" + RLS})
case("public view", {"db/1.sql": RLS + "create view public.v as select * from public.notes;\n"})
case("invoker view", {"db/1.sql": RLS + "create view public.v with (security_invoker = on) as select * from public.notes;\n"})
case("view column named invoker", {"db/1.sql": RLS + "create view public.v (security_invoker) as select id from public.notes;\n"})
case("using true and false", {"db/1.sql": RLS + "create policy own on public.notes for all using (((((true))) and false));\n"})
case("using true or", {"db/1.sql": RLS + "create policy own on public.notes for all using ((true) or auth.uid() = id);\n"})
case("using true cast", {"db/1.sql": RLS + "create policy own on public.notes for all using ((true)::bool);\n"})
case("unclosed quote", {"db/1.sql": RLS + "select 'x;\n"})
# ---- Firebase
case("fb owner only", {"firestore.rules": FB % "if request.auth != null && request.auth.uid == resource.data.owner;"})
case("fb if true", {"firestore.rules": FB % "if true;"})
case("fb test mode", {"firestore.rules": FB % "if request.time < timestamp.date(2026, 12, 31);"})
case("fb true or auth", {"firestore.rules": FB % "if true || request.auth != null;"})
case("fb true and auth", {"firestore.rules": FB % "if true && request.auth != null;"})
case("fb negated group", {"firestore.rules": FB % "if !(request.auth == null || true);"})
case("fb precedence", {"firestore.rules": FB % "if true || false && request.auth != null;"})
case("fb no semicolon nested match", {"firestore.rules": "service cloud.firestore {\n  match /notes/{id} {\n    allow write: if true\n    match /c/{c} { allow read: if request.auth != null; }\n  }\n}\n"})
case("rtdb open", {"database.rules.json": '{"rules": {".read": true, ".write": true}}\n'})
case("rtdb auth", {"database.rules.json": '{"rules": {".read": "auth != null", ".write": "auth != null"}}\n'})
# ---- Q1
case("client key", {"src/components/k.ts": 'export const k = "%s";\n' % KEY})
case("lib key", {"src/lib/k.ts": 'export const k = "%s";\n' % KEY})
case("server only key in components", {"src/components/s.ts": 'import "server-only";\nexport const k = "%s";\n' % KEY})
case("type import next server in pages", {"pages/index.tsx": 'import type { NextRequest } from "next/server";\nexport const sa = {"private_key": "%s"};\n' % PEM})
case("type import next server in vite src", {"src/util.ts": 'import type { NextRequest } from "next/server";\nexport const sa = {"private_key": "%s"};\n' % PEM})
case("long header use client", {"components/x.tsx": "/*\n" + " * license line\n" * 60 + " */\n\"use client\";\nimport type { NextRequest } from \"next/server\";\nexport const sa = {\"private_key\": \"%s\"};\n" % PEM})
case("type import next server in pages, key", {"pages/index.tsx": 'import type { NextRequest } from "next/server";\nexport const k = "%s";\n' % KEY})
case("type import next server in vite src, key", {"src/util.ts": 'import type { NextRequest } from "next/server";\nexport const k = "%s";\n' % KEY})
case("next headers import in components, key", {"src/components/h.ts": 'import { cookies } from "next/headers";\nexport const k = "%s";\n' % KEY})
case("long header use client, key", {"components/x.tsx": "/*\n" + " * license line\n" * 60 + " */\n\"use client\";\nimport \"server-only\";\nexport const k = \"%s\";\n" % KEY})
case("commented server-only import", {"src/components/Checkout.tsx": '/*\nimport "server-only";\n*/\nimport React from "react";\nconst k = "%s";\n' % KEY})
case("template string server-only", {"src/components/Docs.tsx": 'const snippet = `\nimport "server-only";\n`;\nconst k = "%s";\n' % KEY})
case("vite server-only import", {"package.json": '{"dependencies": {"vite": "5", "react": "18"}}', "src/components/Checkout.tsx": 'import "server-only";\nconst k = "%s";\n' % KEY})
case("public lib server-only", {"public/lib.js": "import 'server-only';\nconst k = '%s';\n" % KEY})
case("glob comment balanced by line comment", {"db/1.sql": RLS + "/* uploads land in avatars/* */\nalter table public.notes disable row level security;\n-- old block ended here */\n"})
case("using true is not false", {"db/1.sql": RLS + "create policy p on public.notes for all using ((true) is not false);\n"})
case("using true equals true", {"db/1.sql": RLS + "create policy p on public.notes for all using ((true) = true);\n"})
case("using true or long list", {"db/1.sql": RLS + "create policy p on public.notes for all using ((true) or owner in (" + ", ".join("'u%d'" % i for i in range(700)) + "));\n"})
case("fb true equals true", {"firestore.rules": FB % "if true == true;"})
case("dash dash then string rule", {"db/1.sql": RLS + "comment on table public.notes is $$-- docs: create policy p on public.notes using (true)$$;\n"})
case("function body using true with comment", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\ncreate or replace function public.setup() returns void language plpgsql as $$\nbegin\n  create policy p on public.t for all using (\n    true -- all\n  );\nend $$;\nselect public.setup();\n"})
case("do with comment before tag", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\nDO -- open it up\n$$ BEGIN\n  create policy p on public.t for all using (\n    true -- temp\n  );\nEND $$;\n"})
case("function body disable with block comment", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\ncreate function public.f() returns void language plpgsql as $$ begin alter table public.t disable /* temp */ row level security; end $$;\n"})
case("execute string using true with comment", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\nDO $$ BEGIN EXECUTE 'create policy p on public.t for all using (true /* open */)'; END $$;\n"})
case("backslash quote shifts parity", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\ninsert into public.t values (1, 'O\\'Brien');\ncreate policy p on public.t for all using (\n  true -- all\n);\ninsert into public.t values (2, 'x');\n"})
case("dash dash in policy name, select", {"db/1.sql": RLS + 'create policy "x--y" on public.notes for select\nusing (true);\n'})
case("dash dash in policy name, select same line", {"db/1.sql": RLS + "create policy \"read--all\" on public.notes for select using (true);\n"})
case("dash dash string then select policy", {"db/1.sql": RLS + "comment on table public.notes is 'a -- b';\ncreate policy p on public.notes for select\nusing (true);\n"})
case("comment between for and select", {"db/1.sql": RLS + "create policy p on public.notes for /* reviewed 2026-09: public read is intended */ select using (true);\n"})
case("line comment between for and select", {"db/1.sql": RLS + "create policy p on public.notes for -- anyone may read published notes, reviewed\n  select using (true);\n"})
case("enable after dash dash string", {"db/1.sql": "create table public.t (id int);\ninsert into public.log(m) values ('--'); alter table public.t enable row level security;\n"})
case("enable with long whitespace", {"db/1.sql": "create table public.t (id int);\nalter table public.t" + " " * 30 + "enable row level security;\n"})
case("enable between block comment strings", {"db/1.sql": "create table public.t (id int);\nselect '/*';\nalter table public.t enable row level security;\nselect '*/';\n"})
case("enable in unicode dollar function", {"db/1.sql": "create table public.t (id int);\ncreate function f() returns void as $\u00e9$ select '--'; alter table public.t enable row level security; $\u00e9$ language sql;\n"})
case("disable with long whitespace", {"db/1.sql": RLS + "alter table public.notes disable" + " " * 25 + "row level security;\n"})
case("using true six parens", {"db/1.sql": RLS + "create policy p on public.notes for all using " + "(" * 6 + "true" + ")" * 6 + ";\n"})
case("cts client key", {"src/client/k.cts": 'export const k = "%s";\n' % KEY})
case("rtdb true as string", {"database.rules.json": '{"rules": {".read": "true", ".write": "true"}}\n'})
case("fb ternary then true", {"firestore.rules": FB % "if request.auth == null ? false : request.auth.uid == resource.data.owner || true;"})
case("view text in a comment string", {"db/1.sql": RLS + "comment on table public.notes is 'create view public.v as select 1';\n"})
case("setup.py under tests", {"requirements.txt": "flask\n", "tests/setup.py": "def setup(): pass\n"})
case("setup.py under src", {"requirements.txt": "flask\n", "src/setup.py": "def setup(): pass\n"})
case("setup.py at the root", {"requirements.txt": "flask\n", "setup.py": "from setuptools import setup\nsetup(install_requires=['sentry-sdk'])\n"})
case("mts client key", {"src/components/k.mts": 'export const k = "%s";\n' % KEY})
case("mts server only", {"src/components/s.mts": 'import "server-only";\nexport const k = "%s";\n' % KEY})
case("mcp in roo", {".roo/mcp.json": '{"mcpServers": {}}'})
case("clean app", {})
# ---- Q9
case("sentry vue", {"package.json": '{"dependencies": {"@sentry/vue": "1"}}'})
case("no monitoring", {"package.json": '{"dependencies": {"react": "18"}}'})
case("pipfile", {"package.json": '{"dependencies": {"react": "18"}}', "Pipfile": "sentry-sdk\n"})

# ---- fresh review of 4b7d615 (2026-10-02): text inside strings and quoted names, and 0.3.2's table cap
RLS_T = "create table public.t (id int, name text);\nalter table public.t enable row level security;\n"
FB_P = "service cloud.firestore {\n  match /p/{id} {\n    allow write: if %s;\n  }\n}\n"
case("quoted name, wide disable", {"db/1.sql": RLS_T + 'create index "disable' + " " * 25 + 'row level security" on public.t (id);\n'})
case("quoted name, deep using true", {"db/1.sql": RLS_T + 'create index "using (((((true)))))" on public.t (id);\n'})
case("firebase or true in a list string", {"firestore.rules": FB_P % 'request.auth != null && request.resource.data.tag in ["a||true||b"]'})
case("firebase or true in a string", {"firestore.rules": FB_P % 'request.auth != null && request.resource.data.sep == "||true||"'})
case("firebase or true in a single-quoted string", {"firestore.rules": FB_P % "request.auth != null && resource.data.x == 'y||true'"})
case("firebase open with a string", {"firestore.rules": FB_P % 'request.auth.token.email == "a@b.co" || true'})
case("sql or true in a string", {"db/1.sql": RLS_T + "create policy p on public.t for update using (((((true)) and false)) or name = 'x or true or y');\n"})
case("sql deep and with or true in a string", {"db/1.sql": RLS_T + "create policy p on public.t for update using ((((((true)))) and name = 'a or true or b'));\n"})
case("sql deep open outside strings", {"db/1.sql": RLS_T + "create policy p on public.t for update using ((((((true)))) or name = 'x'));\n"})
case("enables in strings past the table cap", {"db/1.sql": "".join("create table public.t%d (id int);\nalter table public.t%d enable row level security;\n" % (i, i) for i in range(150)) + "insert into notes(body) values ('alter table public.x enable row level security');\n" * 60})

# ---- fresh review of 4b7d615, pass 2 (2026-10-02): where this lexer and 0.3.2's disagree about comments and strings
COPY_T = ("create table public.authors (id int, name text);\nalter table public.authors enable row level security;\n"
          "copy public.authors (id, name) from stdin;\n1\tO'Brien\n\\.\n")
case("dollar inside a table name", {"supabase/migrations/1.sql": RLS_T + "create table public.a$x$ (id int);\n-- old: $x$ alter table public.t disable row level security;\n"})
case("nested block comment", {"db/1.sql": RLS_T + "/* old /* tmp */ '--' alter table public.t disable row level security; */\n"})
case("nested comment then apostrophes", {"db/1.sql": RLS_T + "/* outer /* inner */ it's fine */\n-- don't: alter table public.t disable row level security\n"})
case("copy data then a comment, disable", {"supabase/seed.sql": COPY_T + "-- Don't disable row level security on authors\n"})
case("copy data then a comment, using true", {"supabase/seed.sql": COPY_T + "-- Don't add a policy with using (true) here\n"})
case("sql concatenation, indented", {"db/1.sql": RLS_T + "create policy p on public.t for update using (\n" + " " * 24 + "(true) || name = 'x');\n"})
case("sql concatenation, deep", {"db/1.sql": RLS_T + "create policy p on public.t for update using (((((true)))) || 'a' = 'b');\n"})
case("storage comment markers in strings", {"storage.rules": "service firebase.storage {\n match /b/{bucket}/o {\n  match /{f} {\n   allow write: if (request.resource.contentType.matches('image/*')) && (request.resource.size < 100 || request.resource.name.matches('.*/a') || true);\n  }\n }\n}\n"})
case("firebase true only in a string", {"firestore.rules": FB_P % 'request.auth != null && resource.data.visibility == "true"'})
case("mcp-named skill folder", {".claude/skills/mcp-builder/SKILL.md": "# skill\n", ".cursor/rules/mcp.mdc": "rules\n"})
case("paren inside a sql string, open", {"db/1.sql": RLS_T + "create policy p on public.t for update using ((((((true)))) and name = ')') or true);\n"})
case("table cap boundary, 200 enables", {"db/1.sql": "".join("create table public.t%d (id int);\nalter table public.t%d enable row level security;\n" % (i, i) for i in range(150)) + "insert into notes(body) values ('alter table public.x enable row level security');\n" * 50})

# ---- fresh review of 4b7d615, pass 3 (2026-10-04): every Q3 No from 0.3.2's patterns; the late reading; trimming
FB_X = "service cloud.firestore {\n  match /x/{id} {\n    allow write: if %s;\n  }\n}\n"
case("firebase map literal with or true", {"firestore.rules": FB_X % "request.resource.data == {'public': a || true}"})
case("firebase rule runs into a function", {"firestore.rules": "service cloud.firestore {\n  match /x/{id} {\n    allow write: if isOwner()\n      function helper() { return a || true; }\n  }\n}\n"})
case("nested comment inside a using group", {"db/1.sql": RLS_T + "create policy p on public.t for all using ((((((true)))) /* a /* b */ or true */ and auth.uid() = id));\n"})
case("dollar names across a using group", {"db/1.sql": "create table public.t (id int, owner$q$ uuid, x$q$ int);\nalter table public.t enable row level security;\ncreate policy p on public.t for all using (((((true)))) and owner$q$ = auth.uid());\ncreate policy p2 on public.t for select using (x$q$ is null or true);\n"})
case("copy apostrophe then a quoted policy", {"db/1.sql": RLS_T + "copy t (name) from stdin;\nit's\n\\.\ncomment on table public.t is 'create policy p on public.t for all using ((((((true))))))';\n"})
case("quoted role name hides for select", {"db/1.sql": RLS_T + 'create policy p on public.t for select to "create policy q" using (true);\n'})
case("commented enables past the table cap", {"db/1.sql": "".join("create table public.t%d (id int);\nalter table public.t%d enable row level security;\n" % (i, i) for i in range(150)) + "-- alter table public.x enable row level security;\n" * 60})
case("open write indented 24 spaces after a rule without a semicolon", {"firestore.rules": "service cloud.firestore {\n  match /p/{id} {\n    allow read: if request.auth != null\n" + " " * 24 + "allow write: if request.auth != null || true;\n  }\n}\n"})
case("mcp config inside an instruction folder", {".claude/skills/mcp-github/config.json": "{}"})

# ---- fresh review of 8a6c32b (2026-10-05): 0.3.2's evidence rows, table names, PII rows and partial flag
GLOB = "select '/*'; -- */ "  # 0.3.2 blanked from the `/*` in the string to the `*/` in the comment and read on
case("to anon after a string glob and a comment close", {"db/1.sql": RLS + GLOB + "create policy p on public.notes for select to anon using (auth.uid() = id);\n"})
case("bucket after a string glob and a comment close", {"db/1.sql": RLS + GLOB + "insert into storage.buckets (id, public) values ('a', true);\n"})
case("with check after a string glob and a comment close", {"db/1.sql": RLS + GLOB + "create policy p on public.notes for insert with check (true);\n"})
case("table after a string glob and a comment close", {"db/1.sql": RLS + GLOB + "create table public.u (id int);\n"})
case("legacy table after a commented block", {"supabase/migrations/1.sql": RLS + "create policy r on storage.objects for select using (name like 'avatars/*');\n-- old: /* removed */ create table public.legacy (id int);\n"})
case("table name split by spaces before the dot", {"db/1.sql": "create table public      .notes (id int);\nalter table public.notes enable row level security;\n"})
case("create table if with long whitespace", {"db/1.sql": "create table if" + " " * 25 + "not exists public.notes (id int);\nalter table public.notes enable row level security;\n"})
case("table name on the next line", {"db/1.sql": "create table public.\n        profiles (id uuid primary key);\nalter table public.profiles enable row level security;\n"})
case("pii after a string glob and a comment close", {"supabase/migrations/1.sql": "create table patients (id int, note text default '/*' -- legacy */, ssn text, diagnosis text);\n"})
case("pii after a dash dash string", {"supabase/migrations/1.sql": "create table public.notes (id int, note text default '--', diagnosis text);\nalter table public.notes enable row level security;\n"})
case("mts only", {"src/index.mts": "export const a = 1\n"}, base=False)
case("cts server with a manifest", {"server/index.cts": "module.exports = 1\n", "package.json": '{"name": "x"}\n'}, base=False)
case("env file compressed with zstd", {".env.zst": "NEXT_PUBLIC_OPENAI_SECRET_KEY=" + KEY + "\n", "src/a.ts": "export const x = 1\n"})
case("env local file compressed with zstd", {".env.local.zst": "NEXT_PUBLIC_OPENAI_SECRET_KEY=" + KEY + "\n", "src/a.ts": "export const x = 1\n"})
case("firebase allow without a condition", {"firestore.rules": "service cloud.firestore {\n  match /x/{id} {\n    allow read, write;\n  }\n}\n"})
case("firebase allow read without a condition", {"firestore.rules": "service cloud.firestore {\n  match /x/{id} {\n    allow read;\n  }\n}\n"})
SEG, FSEG = "é" * 90, "é" * 62
TRIM = {"supabase/migrations/1.sql": RLS}  # 0.3.2's output goes over the cap and is trimmed: partial
TRIM.update({"a%d/%s/%s/Pipfile" % (i, SEG, SEG): "x\n" for i in range(5)})
TRIM.update({"z%d/%s/%s/health.ts" % (i, SEG, SEG): "export const x = 1;\n" for i in range(12)})
TRIM.update({"m%d/%s/%s/%s/schema.prisma" % (i, FSEG, FSEG, FSEG): "model U {\n email String\n phone String\n}\n" for i in range(12)})
case("output over the cap with manifests the release did not read", TRIM)

# ---- fresh review of b1188dc, cycle 2 (2026-10-06): seven ways 0.3.3's own fixes were worse than 0.3.2
FIELDS = ["email", "phone", "ssn", "dob", "address", "street", "postal_code", "passport", "iban", "medical", "diagnosis", "salary"]


def _long(e):
    """`e` "é" as two folders: each "é" is six bytes of JSON but two on disk, and Linux allows 255 bytes per name."""
    return "é" * (e // 2) + "/" + "é" * (e - e // 2)


def near_cap(e, extra, health=11, auth=2, tail=None):
    """0.3.2's output a few bytes either side of its 30,000-byte cap: long folder names (each "é" is six bytes of JSON)
    in health routes (Q9), one-field schemas (Q10) and auth folders (Q4); `tail` ASCII characters fine-tune it."""
    f = {}
    for i in range(health):
        f["h%02d/%s/a/health.ts" % (i, _long(e))] = "export const x = 1;\n"
    for i, field in enumerate(FIELDS):
        f["m%02d/%s/schema.prisma" % (i, _long(e))] = "model U%d {\n %s String\n}\n" % (i, field)
    for i in range(auth):
        f["auth/%d%s/x.ts" % (i, _long(e))] = "export const x = 1;\n"
    if tail:
        f["hz/%s/health.ts" % ("a" * tail)] = "export const x = 1;\n"
    f.update(extra)
    return f


case("compressed env template with a browser secret", {".env.example.zst": "NEXT_PUBLIC_OPENAI_SECRET_KEY=" + KEY + "\n"})
case("private key in a zst file", {"x.zst": PEM})
case("private key in a pem.zst file", {"key.pem.zst": PEM})
case("firestore test mode just over the cap", near_cap(176, {"firestore.rules": "rules_version = '2';\nservice cloud.firestore {\n  match /databases/{database}/documents {\n    match /{document=**} {\n      allow read, write: if request.time < timestamp.date(2026, 12, 1);\n    }\n  }\n}\n"}))
case("open read rows the release never gave, just under the cap", near_cap(174, {"database.rules.json": '{"rules": {".read": "true", ".write": "true"}}\n', "db/1.sql": "create table public.t (id int);\n"}, tail=68))
case("pii field just under the cap", near_cap(190, {"supabase/migrations/1.sql": RLS + "create table public.people (id int, ssn text);\nalter table public.people enable row level security;\n"}, health=9, auth=3, tail=72))
case("opencode.jsonc counts toward max files", {"src/app.ts": "export const x = 1\n", "package.json": '{"dependencies": {"react": "18"}}\n', "opencode.jsonc": "{}\n"}, base=False, args={"max_files": 2})
case("private key in a public opencode.jsonc", {"public/opencode.jsonc": "{PEM_BODY}"})
case("oversize mts", {"src/big.mts": {"repeat": "export const a = 1;\n", "times": 30000}})
case("hard-linked mts", {"src/a.mts": "export const x = 1\n"}, links={"src/b.mts": "src/a.mts"})

# ---- fresh review of d90c4fd (2026-10-12): string contents printed where 0.3.2 printed none; "hunter2" marks
# text inside a string, a function body or a quoted name (NeverWorseThanMainTests.test_never_prints_text_the_baseline_did_not)
FBR = "rules_version = '2';\nservice cloud.firestore {\n  match /databases/{database}/documents {\n    match /x/{id} {\n      %s\n    }\n  }\n}\n"
TAG = "$" + "a" * 70 + "$"
case("rules mask: a quote in a comment and a comment across two strings", {"firestore.rules": FBR % "allow read: if /* \" */ request.auth.uid == \"p /* q\" || 'r */ s' == \"hunter2-pw jane.doe@example.com\" || true;"})
case("rules mask: a comment opener in a string, a quote in a comment", {"firestore.rules": FBR % "allow read: if resource.data.p == '/*' /* don't */ || resource.data.pw == 'hunter2!prod' || true;"})
case("rules mask: mirrored quotes on two lines", {"firestore.rules": FBR % ("allow read: if a == '/*' || b == \"*/\" /* ' */ || c == 'hunter2aaa' || true;\n"
                                                                       "      allow write: if a == \"/*\" || b == '*/' /* \" */ || c == \"hunter2bbb\" || true;")})
case("rules mask: a quote inside a comment only", {"firestore.rules": FBR % "allow read: if resource.data.k == /* \" */ \"hunter2Pass_word\" || true;"})
case("dollar tag longer than a name", {"supabase/migrations/1.sql": RLS + "create function f() returns void language plpgsql as " + TAG +
                                       " begin drop table public.hunter2tbl; create view public.hunter2view as select 1; end " + TAG + ";\n"})
case("dollar tag opened right after one closes", {"supabase/migrations/1.sql": RLS + "create function g() returns void as $a$x$a$$b$ begin drop table public.hunter2_second; end $b$ language plpgsql;\n"})
case("dollar signs inside a name before a function body", {"supabase/migrations/1.sql": RLS + "create table public.x$$b$ (id int);\ncreate function f() returns void as $b$ drop table public.hunter2tbl; $b$;\n"})
case("a name ending in $e before a string", {"supabase/migrations/1.sql": RLS + "create policy p on public.notes using (pw = x$e'--\\' or pw = 'hunter2prod' /* ' */) to anon;\n"})
case("nested block comment around a string", {"supabase/migrations/1.sql": RLS + "create policy p on public.notes using (/* /* */ ' -- */ pw = 'x' or pw = 'hunter2prod' /* ' */) to anon;\n"})
case("quoted view name", {"supabase/migrations/1.sql": RLS + 'create view "jane hunter2 view" as select 1;\n'})
MIG = "supabase/migrations/1.sql"
case("quoted dropped table", {MIG: RLS + 'drop table "hunter2";\n'})
case("quoted view", {MIG: RLS + 'create view "hunter2" as select 1;\n'})
case("comma inside a quoted dropped name", {MIG: RLS + 'drop table "Jane Doe,hunter2_ssn";\n'})
case("E string right after a dollar quote", {MIG: RLS + "select $a$x$a$e'\\' ; drop table hunter2; create view hunter2v as select 1; ';\n"})
case("block comment that does not nest", {MIG: RLS + "/* Don't edit: generated from src/*.sql */\ninsert into log values ('drop table hunter2;');\ninsert into log values ('create view hunter2v as select 1;');\n"})
case("non-ascii dollar tag", {MIG: RLS + "create function f() returns void as $€$ drop table hunter2; $€$ language sql;\n"})
case("dollar tag after a parameter", {MIG: RLS + "select $1$x$ drop table hunter2; $x$;\n"})
case("quoted name over two lines", {MIG: RLS + 'select "x\ndrop table hunter2; ";\n'})
case("E string after a non-ascii name", {MIG: RLS + "select €E'\\' x ' drop table hunter2; ';\n"})
case("table and enable only inside a string", {MIG: RLS + "insert into t values ('create table hunter2tbl (id int); alter table hunter2tbl enable row level security');\n"})
case("long dollar tag right after one closes", {MIG: RLS + "create function g() returns void as $a$x$a$" + TAG + " begin drop table public.hunter2x; end " + TAG + " language plpgsql;\n"})
case("rls enable only inside a string for a quoted table", {MIG: 'create table public."Hunter2 Secret" (id int);\nselect \'alter table public."Hunter2 Secret" enable row level security\';\n'})
case("a table only the overlay reads", {MIG: "create table" + " " * 30 + "public.hunter2 (id int);\n"})
case("monitoring family with free text", {"package.json": '{"dependencies": {"react": "18", "@sentry/hunter2-x jane.doe@example.com": "1"}}\n'})
case("monitoring family in requirements", {"requirements.txt": "opentelemetry-hunter2pw==1.0\n"})
case("rls words inside a comment string",{"db/1.sql": RLS + "comment on table public.notes is 'disable                row level security';\n"
                                           "comment on column public.notes.id is 'doc says using (((((true))))) is bad';\n"})


# S-044: a DO-block loop that turns RLS on. Credited shapes are softer than 0.3.2 on purpose (ALLOW_SOFTER);
# every near miss must stay flagged.
LOOP_TABLES = "create table public.notes (id int);\ncreate table public.tasks (id int);\n"
def _loop(names="'notes','tasks'", fmt="'alter table public.%I enable row level security'", arg="t", head="do $$", tail="end $$;"):
    return ("%s\ndeclare t text;\nbegin\n  foreach t in array array[%s]\n  loop\n    execute format(%s, %s);\n"
            "    execute format('alter table public.%%I force row level security', t);\n  end loop;\n%s\n" % (head, names, fmt, arg, tail))
LOOP_A, LOOP_B = "supabase/migrations/20261010000000_a.sql", "supabase/migrations/20261017000000_b.sql"
case("rls loop credited", {LOOP_A: LOOP_TABLES + _loop()})
case("rls loop credited across lines without schema", {LOOP_A: LOOP_TABLES + _loop(names="'notes',\n   'tasks'", fmt="'ALTER TABLE %I ENABLE ROW LEVEL SECURITY'")})
case("rls loop credited after an earlier create", {LOOP_A: LOOP_TABLES, LOOP_B: _loop()})
case("rls loop missing a table", {LOOP_A: LOOP_TABLES + _loop(names="'notes'")})
case("rls loop arg not the loop variable", {LOOP_A: LOOP_TABLES + _loop(arg="'notes'")})
case("rls loop two placeholders", {LOOP_A: LOOP_TABLES + _loop(fmt="'alter table %I.%I enable row level security'", arg="'public', t")})
case("rls loop quote_ident concatenation", {LOOP_A: LOOP_TABLES + _loop().replace("execute format('alter table public.%I enable row level security', t)", "execute 'alter table public.' || quote_ident(t) || ' enable row level security'")})
case("rls loop array from a variable", {LOOP_A: LOOP_TABLES + _loop(names="").replace("array array[]", "array names")})
case("rls loop array from a query", {LOOP_A: LOOP_TABLES + _loop(names="").replace("array array[]", "array (select array_agg(tablename) from pg_tables)")})
case("rls loop mixed-case names", {LOOP_A: LOOP_TABLES + _loop(names="'Notes','Tasks'")})
case("rls loop in a function body", {LOOP_A: LOOP_TABLES + _loop(head="create function f() returns void language plpgsql as $$")})
case("rls loop inside a string", {LOOP_A: LOOP_TABLES + "comment on table public.notes is '" + _loop().replace("'", "''") + "';\n"})
case("rls loop format is not only the enable", {LOOP_A: LOOP_TABLES + _loop(fmt="'alter table public.%I enable row level security; select 1'")})
case("rls loop then a later disable", {LOOP_A: LOOP_TABLES + _loop(), LOOP_B: "alter table public.notes disable row level security;\n"})
case("rls loop then a later drop", {LOOP_A: LOOP_TABLES + _loop(), LOOP_B: "drop table public.notes;\n"})
case("rls loop then a later create", {LOOP_A: LOOP_TABLES + _loop(), LOOP_B: "create table public.notes (id int);\n"})
# Review round 1 (Codex P1, state machines): a loop that might not run, or a scan that may have missed a later
# disable, gets no credit. Not in ALLOW_SOFTER: these must equal the release.
case("rls loop inside an if", {LOOP_A: LOOP_TABLES + _loop().replace("begin\n", "begin\nif current_setting('app.rls', true) = 'on' then\n", 1).replace("  end loop;\n", "  end loop;\nend if;\n", 1)})
case("rls loop with an exit", {LOOP_A: LOOP_TABLES + _loop().replace("  end loop;", "    exit;\n  end loop;", 1)})
case("rls loop plus an unread larger migration", {LOOP_A: LOOP_TABLES + _loop(), LOOP_B: "alter table public.notes disable row level security;\n" + "-- pad\n" * 2000}, args={"max_file_bytes": 8192})
case("rls loop past the five-table cap", {LOOP_A: "".join("create table public.t%d (id int);\n" % i for i in range(8)) + _loop(names="'t0','t1','t2'")})


# S-064 (custody 0.6.2): browser-prefixed secret names in screen code, and live keys typed into code
VITE_PKG = {"package.json": '{"dependencies": {"vite": "5", "openai": "4"}}\n'}
case("vite openai name in screen code", dict(VITE_PKG, **{"src/lib/ai.ts": 'import OpenAI from "openai";\nexport const ai = new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_API_KEY, dangerouslyAllowBrowser: true });\n'}))
case("vite service role name in screen code", dict(VITE_PKG, **{"src/db.ts": "export const k = import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY;\n"}))
case("live key typed into a python server file", {"app/pay.py": 'import stripe\nstripe.api_key = "%s"\n' % LIVE})
case("live key typed into an api route", {"api/pay.ts": 'export const k = "%s";\n' % LIVE})
case("next server component reads a public secret name", {"package.json": '{"dependencies": {"next": "14"}}\n', "app/page.tsx": "export default function P() { return process.env.NEXT_PUBLIC_OPENAI_API_KEY ? 1 : 0 }\n"})
case("seed script reads a browser-prefixed service name", dict(VITE_PKG, **{"scripts/seed.ts": "const k = process.env.VITE_SUPABASE_SERVICE_ROLE_KEY;\n"}))
case("ai flag with an unknown name", dict(VITE_PKG, **{"src/ai.ts": "new OpenAI({ apiKey: import.meta.env.VITE_MY_AI, dangerouslyAllowBrowser: true });\n"}))
case("clean vite app with public names", dict(VITE_PKG, **{"src/db.ts": "export const u = import.meta.env.VITE_SUPABASE_URL;\nexport const a = import.meta.env.VITE_SUPABASE_ANON_KEY;\n"}))
case("env name already judged plus two screen files", dict(VITE_PKG, **{".env": "VITE_OPENAI_API_KEY=%s\n" % KEY, "src/a.ts": "export const k = import.meta.env.VITE_OPENAI_API_KEY;\n", "src/b.ts": "export const k = import.meta.env.VITE_OPENAI_API_KEY;\n"}))
case("stripe test key in a server file", {"server/pay.ts": 'export const k = "sk_test_a1b2c3d4e5f6g7h8i9j0";\n'})
# S-064 /review red team: hand-built hostile inputs the branch first made slow or broke
case("unclosed quote with many escaped quotes", dict(VITE_PKG, **{"src/big.js": "const k = import.meta.env.VITE_OPENAI_API_KEY;\nconst s = \"" + "\\\"" * 40000 + "\n"}))
case("deeply nested package json", {"package.json": '{"a":' * 5000 + "1" + "}" * 5000, "src/a.ts": "export const a = 1;\n"})


def answers(scanner, c):
    tmp = tempfile.mkdtemp()
    try:
        materialize(os.path.join(tmp, "app"), c)
        flags = []
        for k, v in sorted(c.get("args", {}).items()):
            flags += ["--" + k.replace("_", "-"), str(v)]
        out = subprocess.run([sys.executable, "-I", scanner, "--repo", "app"] + flags, cwd=tmp, capture_output=True, text=True).stdout
        r = json.loads(out)
        q = r["questions"]
        pii = sorted(set(e["snippet"] for e in q["q10"]["evidence"] if e["check"] == "pii-field"))
        return {k: q[k]["answer"] for k in ("q1", "q3", "q9")}, r["partial"], pii
    finally:
        shutil.rmtree(tmp)

if __name__ == "__main__":
    ref, out_path = sys.argv[1], sys.argv[2]
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=os.path.dirname(os.path.abspath(__file__)),
                          capture_output=True, text=True, check=True).stdout.strip()
    tmp = tempfile.mkdtemp()
    try:
        scanner, sha = export_release(ref, tmp, root)
        version = subprocess.run([sys.executable, "-I", scanner, "--version"], capture_output=True, text=True).stdout.strip()
        for c in cases:
            c["main"], c["main_partial"], c["main_pii"] = answers(scanner, c)
    finally:
        shutil.rmtree(tmp)
    with open(out_path, "w") as fh:
        json.dump({"baseline": "custody-check %s (main %s)" % (version, sha[:7]), "baseline_sha": sha, "cases": cases},
                  fh, indent=1, sort_keys=True)
    print(len(cases), "cases written")
