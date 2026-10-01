"""Build cases.json for NeverWorseThanMainTests: realistic files plus every repro from review, with the answers
the released baseline scanner gives on them (Q1, Q3, Q9), and every check per question that is not evidence-only.

Usage: git show <release>:custody-check/skills/custody-check/scripts/custody_scan.py > /tmp/baseline.py
       python3 build_cases.py /tmp/baseline.py cases.json

Add a case for every input a review finds; regenerate from the new release after each merge."""
import importlib.util, json, os, shutil, subprocess, sys, tempfile

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
case("function body using true with comment", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\ncreate or replace function public.setup() returns void language plpgsql as $$\nbegin\n  create policy p on public.t for all using (\n    true -- all\n  );\nend $$;\nselect public.setup();\n"})
case("do with comment before tag", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\nDO -- open it up\n$$ BEGIN\n  create policy p on public.t for all using (\n    true -- temp\n  );\nEND $$;\n"})
case("function body disable with block comment", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\ncreate function public.f() returns void language plpgsql as $$ begin alter table public.t disable /* temp */ row level security; end $$;\n"})
case("execute string using true with comment", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\nDO $$ BEGIN EXECUTE 'create policy p on public.t for all using (true /* open */)'; END $$;\n"})
case("backslash quote shifts parity", {"db/1.sql": "create table public.t (id int);\nalter table public.t enable row level security;\ninsert into public.t values (1, 'O\\'Brien');\ncreate policy p on public.t for all using (\n  true -- all\n);\ninsert into public.t values (2, 'x');\n"})
case("mts client key", {"src/components/k.mts": 'export const k = "%s";\n' % KEY})
case("mts server only", {"src/components/s.mts": 'import "server-only";\nexport const k = "%s";\n' % KEY})
case("mcp in roo", {".roo/mcp.json": '{"mcpServers": {}}'})
case("clean app", {})
# ---- Q9
case("sentry vue", {"package.json": '{"dependencies": {"@sentry/vue": "1"}}'})
case("no monitoring", {"package.json": '{"dependencies": {"react": "18"}}'})
case("pipfile", {"package.json": '{"dependencies": {"react": "18"}}', "Pipfile": "sentry-sdk\n"})

# ---- Q5 code half: a workflow is a deploy path only when a command deploys (#16)
W = ".github/workflows/%s.yml"
STEPS = "on: push\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n%s"
def wf(name, steps, file="deploy"):
    case(name, {W % file: STEPS % steps})
wf("workflow lint only", "      - run: npm run lint\n", "ci")
wf("workflow review bot only", "      - uses: anthropics/claude-code-action@v1\n", "pr-bot")
wf("workflow environment key only", "      - run: npm test\n    environment: test\n")
wf("workflow named deploy, no deploy step", "      - run: npm ci\n")
wf("workflow commented deploy", "      # - run: vercel deploy --prod\n      - run: npm test\n")
wf("workflow echo mentions deploy", "      - name: firebase deploy\n        run: echo \"remember to firebase deploy by hand\"\n")
wf("workflow vercel build only", "      - run: npx vercel build --prod\n      - run: vercel pull --yes\n")
wf("workflow install then prod flag", "      - run: npm i -g vercel && pnpm install --prod\n")
wf("workflow vercel word then prod flag", "      - run: echo vercel rocks && npm run build -- --prod\n")
wf("workflow comment then split deploy", "      - run: |\n          true # ; vercel deploy --prod\n")
case("workflow disabled job", {W % "off": "on: push\njobs:\n  d:\n    if: false\n    steps:\n      - run: vercel deploy --prod\n"})
case("workflow in subfolder", {".github/workflows/archive/old.yml": STEPS % "      - run: vercel deploy --prod\n"})
wf("workflow vercel prod", "      - run: npx vercel --prod --token=${{ secrets.VERCEL_TOKEN }}\n")
wf("workflow vercel pinned", "      - run: npx --yes vercel@latest deploy\n")
wf("workflow vercel local bin", "      - run: ./node_modules/.bin/vercel deploy --prod\n")
wf("workflow netlify", "      - run: netlify deploy --prod\n")
wf("workflow wrangler action", "      - uses: cloudflare/wrangler-action@v3\n")
wf("workflow firebase", "      - run: firebase deploy --only hosting\n")
wf("workflow fly", "      - run: flyctl deploy --remote-only\n")
wf("workflow block scalar", "      - run: |\n          npm ci\n          echo 'build #1'; vercel deploy --prod\n")
wf("workflow pages action", "      - uses: actions/deploy-pages@v4\n")
# ---- Q8: a model name is a hint only near a provider (#17)
case("model name in research script", {"scripts/research.py": 'MODELS = ["gpt-4o", "claude-3-opus", "gemini-1.5-pro"]\n'})
case("model name in ui copy", {"src/copy.ts": 'export const blurb = "Built with gpt-4o";\n'})
case("model name in json data", {"data/bench.json": '{"models": ["gpt-4o"]}\n'})
case("model name with sdk import", {"src/ai.ts": 'import OpenAI from "openai";\nconst m = "gpt-4o";\n'})
case("model name with python sdk", {"app/llm.py": 'from anthropic import Anthropic\nMODEL = "claude-3-5-sonnet"\n'})
case("model name with provider host", {"src/f.ts": 'await fetch("https://api.anthropic.com/v1/messages", {body: JSON.stringify({model: "claude-3-haiku"})});\n'})
case("model name with provider key", {"src/k.ts": 'const k = process.env.OPENAI_API_KEY;\nconst m = "gpt-4o";\n'})
case("deno npm import", {"supabase/functions/chat/index.ts": 'import OpenAI from "npm:openai@4.20.0";\nconst m = "gpt-4o";\n'})
case("esm.sh import", {"supabase/functions/a/index.ts": 'import Anthropic from "https://esm.sh/@anthropic-ai/sdk@0.20.0";\nconst m = "claude-3-haiku";\n'})
case("lovable gateway", {"supabase/functions/lov/index.ts": 'await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {body: JSON.stringify({model: "google/gemini-2.5-flash"})});\n'})
case("lovable key", {"supabase/functions/key/index.ts": 'const k = Deno.env.get("LOVABLE_API_KEY");\nconst m = "gemini-2.5-flash";\n'})
case("bedrock client", {"app/br.py": 'import boto3\nc = boto3.client("bedrock-runtime")\nm = "claude-3-sonnet"\n'})
case("newer sdk import", {"package.json": '{"dependencies": {"@ai-sdk/gateway": "1.0.0"}}', "src/g.ts": 'import { gateway } from "@ai-sdk/gateway";\nconst m = "gpt-4o";\n'})
case("lookalike import", {"src/f.ts": 'import x from "ai-utils";\nconst m = "gpt-4o";\n', "app/f.py": 'import openai_helpers\nm = "gpt-4o"\n'})
case("mentions before a real call", dict({"src/m%d.ts" % i: "".join('const a%d = "gpt-4o-%d";\n' % (j, j) for j in range(5)) for i in range(3)},
                                         **{"src/zz_ai.ts": 'import OpenAI from "openai";\nconst r = {model: "gpt-4o", max_tokens: 100};\n'}))

# ---- review cycle 2 for #16/#17
case("model name in a config file, call elsewhere", {"src/lib/config.ts": 'export const MODEL = "gpt-4o-mini";\n',
                                                    "src/lib/ai.ts": 'import { MODEL } from "./config";\nawait fetch("https://api.openai.com/v1/chat/completions", {body: JSON.stringify({model: MODEL})});\n'})
case("azure openai sdk", {"src/az.ts": 'import { AzureOpenAI } from "@azure/openai";\nconst m = "gpt-4o";\n'})
case("anthropic bedrock sdk", {"src/b.ts": 'import { AnthropicBedrock } from "@anthropic-ai/bedrock-sdk";\nconst m = "claude-3-haiku";\n'})
case("vertex sdk", {"src/v.ts": 'import { VertexAI } from "@google-cloud/vertexai";\nconst m = "gemini-1.5-pro";\n'})
case("wrapper module", {"src/app/page.tsx": 'import { client } from "@/lib/llm";\nconst m = "gpt-4o";\n'})
case("python requests to an endpoint", {"app/call.py": "requests.post(os.environ['LLM_ENDPOINT'], json={'model': 'gpt-4o'})\n"})
case("model name in docs snippet", {"docs/snippets/a.ts": 'const m = "gpt-4o";\n'})
case("model name in a test", {"tests/test_prompts.py": 'MODEL = "gpt-4o"\n'})
wf("workflow npm run deploy", "      - run: npm run deploy\n")
wf("workflow deploy shell script", "      - run: ./scripts/deploy.sh production\n")
wf("workflow separator inside quotes", "      - run: echo \"done; vercel deploy --prod\"\n      - run: git commit -m 'x && vercel --prod'\n")
wf("workflow run with no space", "      - run:vercel deploy --prod\n")
case("workflow crlf if false", {W % "off": "on: push\r\njobs:\r\n  d:\r\n    if: false\r\n    steps:\r\n      - run: vercel deploy --prod\r\n"})

# ---- review cycle 3 for #16/#17
for rel in ("app/docs/page.tsx", "pages/docs/index.tsx", "src/scripts/llm.ts", "apps/docs/app/page.tsx", "app/evals/route.ts", "server/scripts/ai.py"):
    case("model name in app route " + rel, {rel: 'm = "gpt-4o"\n'})
case("python import list with openai", {"scripts/a.py": "import os, openai\nm = 'gpt-4o'\n"})
case("js import across lines", {"scripts/b.ts": 'import OpenAI from\n  "openai";\nconst m = "gpt-4o";\n'})
case("ruby require openai", {"scripts/c.rb": 'require "openai"\nm = "gpt-4o"\n'})
wf("workflow env then deploy script", "      - run: DEPLOY_TOKEN=abc ./scripts/deploy.sh x\n")
wf("workflow apostrophe then deploy", "      - run: echo don't && vercel deploy --prod\n")
wf("workflow predeploy only", "      - run: ./scripts/predeploy.sh\n      - run: ./scripts/undeploy.sh\n      - run: bash deploy_test.sh\n")
wf("workflow hostile label line", "      - run: vercel deploy " + "app " * 2000 + "x " + "--prebuilt " * 2000 + "\n")

def answers(scanner, files):
    tmp = tempfile.mkdtemp()
    try:
        app = os.path.join(tmp, "app")
        for rel, body in files.items():
            p = os.path.join(app, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            for k, v in REAL.items():
                body = body.replace(k, v)
            open(p, "w", newline="").write(body)
        out = subprocess.run([sys.executable, "-I", scanner, "--repo", "app"], cwd=tmp, capture_output=True, text=True).stdout
        q = json.loads(out)["questions"]
        return {k: q[k]["answer"] for k in ("q1", "q3", "q9")}, strong_checks(q)
    finally:
        shutil.rmtree(tmp)

spec = importlib.util.spec_from_file_location("baseline", MAIN)
BASELINE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASELINE)

def strong_checks(q):
    """Per question, the checks that change an answer or that the skill leads with: every effect except evidence."""
    halves = {"q5.code": q["q5"]["code"], "q5.data": q["q5"]["data"]}
    halves.update({k: v for k, v in q.items() if k != "q5"})
    return {k: sorted({e["check"] for e in v["evidence"] if BASELINE.CHECKS[e["check"]][1] != "evidence"}) for k, v in sorted(halves.items())}

for c in cases:
    c["main"], c["main_checks"] = answers(MAIN, c["files"])
json.dump({"baseline": sys.argv[3] if len(sys.argv) > 3 else "unrecorded", "cases": cases}, open(OUT, "w"), indent=1, sort_keys=True)
print(len(cases), "cases written")
