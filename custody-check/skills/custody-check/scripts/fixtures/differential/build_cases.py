"""Build cases.json for NeverWorseThanMainTests: realistic files plus every repro from review, with the answers
the released baseline scanner gives on them (Q1, Q3, Q9).

Usage: git show <release>:custody-check/skills/custody-check/scripts/custody_scan.py > /tmp/baseline.py
       python3 build_cases.py /tmp/baseline.py cases.json

Add a case for every input a review finds; regenerate from the new release after each merge."""
import json, os, shutil, subprocess, sys, tempfile

MAIN = sys.argv[1]
OUT = sys.argv[2]

A = "src/components/A.tsx"
BASE = {A: "export const A = () => null;\n"}
RLS = "create table public.notes (id int);\nalter table public.notes enable row level security;\n"
FB = "service cloud.firestore {\n  match /databases/{db}/documents {\n    match /{doc=**} {\n      allow read, write: %s\n    }\n  }\n}\n"
KEY = "{KEY}"  # filled in at run time: no key-shaped literal is stored in the repo
PEM = "{PEM}"
REAL = {"{KEY}": "sk-" + "proj-" + "a1b2c3d4e5f6g7h8i9j0" * 2,
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

for c in cases:
    c["main"], c["main_partial"], c["main_pii"] = answers(MAIN, c)
json.dump({"baseline": sys.argv[3] if len(sys.argv) > 3 else "unrecorded", "cases": cases}, open(OUT, "w"), indent=1, sort_keys=True)
print(len(cases), "cases written")
