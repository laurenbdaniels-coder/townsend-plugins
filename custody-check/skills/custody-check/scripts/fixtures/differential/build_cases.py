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
        "{PEM}": "-----BEGIN " + "PRIVATE KEY-----\\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\\n-----END " + "PRIVATE KEY-----\\n"}

cases = []
def case(name, files):
    cases.append({"name": name, "files": dict(BASE, **files)})

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
case("mts client key", {"src/components/k.mts": 'export const k = "%s";\n' % KEY})
case("mts server only", {"src/components/s.mts": 'import "server-only";\nexport const k = "%s";\n' % KEY})
case("mcp in roo", {".roo/mcp.json": '{"mcpServers": {}}'})
case("clean app", {})
# ---- Q9
case("sentry vue", {"package.json": '{"dependencies": {"@sentry/vue": "1"}}'})
case("no monitoring", {"package.json": '{"dependencies": {"react": "18"}}'})
case("pipfile", {"package.json": '{"dependencies": {"react": "18"}}', "Pipfile": "sentry-sdk\n"})

def answers(scanner, files):
    tmp = tempfile.mkdtemp()
    try:
        app = os.path.join(tmp, "app")
        for rel, body in files.items():
            p = os.path.join(app, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            for k, v in REAL.items():
                body = body.replace(k, v)
            open(p, "w").write(body)
        out = subprocess.run([sys.executable, "-I", scanner, "--repo", "app"], cwd=tmp, capture_output=True, text=True).stdout
        q = json.loads(out)["questions"]
        return {k: q[k]["answer"] for k in ("q1", "q3", "q9")}
    finally:
        shutil.rmtree(tmp)

for c in cases:
    c["main"] = answers(MAIN, c["files"])
json.dump({"baseline": sys.argv[3] if len(sys.argv) > 3 else "unrecorded", "cases": cases}, open(OUT, "w"), indent=1, sort_keys=True)
print(len(cases), "cases written")
