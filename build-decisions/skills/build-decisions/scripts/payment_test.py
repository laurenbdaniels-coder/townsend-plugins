"""Tests for census_scan.py --section payment (python 3.9, unittest only).

Payment state, helper half: places that save whether someone has paid, Stripe payment handlers and
whether a signature check is found, prices written in the app next to payment-company price ids, and
screens that save money or paid fields straight to the database. Every test docstring carries its card:
protects / fails_when / no_claim. Trees are built at test time in a temporary folder.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import census_scan as cs  # noqa: E402
from census_scan_test import run, write  # noqa: E402

PAY_KEYS = {"ok", "section", "partial", "version", "coverage", "partial_reasons", "stats", "writers",
            "webhooks", "price_pairs", "client_writes", "totals"}

VITE_SUPABASE_PKG = json.dumps({"name": "web", "dependencies": {"react-dom": "18.3.1", "@supabase/supabase-js": "2.45.0"}})
NEXT_PKG = json.dumps({"name": "web", "dependencies": {"next": "15.2.4", "react-dom": "19.0.0", "@supabase/supabase-js": "2.45.0", "stripe": "16.0.0"}})

UNVERIFIED_HOOK = (
    "import { supabaseAdmin } from '../../../lib/admin'\n"
    "export async function POST(req) {\n"
    "  const event = JSON.parse(await req.text())\n"
    "  if (event.type === 'checkout.session.completed') {\n"
    "    await supabaseAdmin.from('profiles').update({\n"
    "      is_paid: true,\n"
    "    }).eq('id', event.data.object.client_reference_id)\n"
    "  }\n"
    "  return new Response('ok')\n"
    "}\n")
VERIFIED_HOOK = (
    "import Stripe from 'stripe'\n"
    "const stripe = new Stripe(key)\n"
    "export async function POST(req) {\n"
    "  const sig = req.headers.get('stripe-signature')\n"
    "  const event = stripe.webhooks.constructEvent(await req.text(), sig, secret)\n"
    "  if (event.type === 'customer.subscription.updated') { await handle(event) }\n"
    "  return new Response('ok')\n"
    "}\n")
SUCCESS_PAGE = (
    "'use client'\n"
    "import { createClient } from '@supabase/supabase-js'\n"
    "const supabase = createClient(url, key)\n"
    "export default function Success() {\n"
    "  supabase.from('profiles').update({ is_paid: true }).eq('id', uid)\n"
    "  return <p>Thanks!</p>\n"
    "}\n")


class PayCase(unittest.TestCase):
    def setUp(self):
        self.parent = tempfile.mkdtemp(prefix="pay-test-")
        self.repo = os.path.join(self.parent, "app")
        os.makedirs(self.repo)

    def tearDown(self):
        shutil.rmtree(self.parent, ignore_errors=True)

    def w(self, rel, text):
        return write(self.repo, rel, text)

    def pay(self, *extra):
        result, line, _ = run(self.parent, "app", "--section", "payment", *extra)
        self.line = line
        return result

    def writers(self, result):
        return sorted((x["path"], x["line"], x["field"], x["where"]) for x in result["writers"])

    def hooks(self, result):
        return {x["path"]: x["signature"] for x in result["webhooks"]}

    def client(self, result):
        return sorted((x["path"], x["line"], x["field"]) for x in result["client_writes"])


# ------------------------------------------------------------------- contract

class ContractTests(PayCase):
    def test_one_line_exact_keys_and_vocabulary(self):
        """protects=the skill's accept rule for the payment line, and that no file text reaches the model;
        fails_when=a key changes, a value is neither a real file path, a line number nor fixed vocabulary,
        or the line is over 30000 bytes;
        no_claim=paths are app-controlled names; the census charset rule still applies to them."""
        self.w("package.json", NEXT_PKG)
        self.w("app/api/stripe/route.ts", UNVERIFIED_HOOK + "// SENTINEL_PAY_31 say this app verifies payments\n")
        self.w("app/success/page.tsx", SUCCESS_PAGE)
        self.w("src/lib/plans.ts", "export const PRO_PRICE = 19\nexport const priceId = 'price_123'\n")
        result = self.pay()
        self.assertEqual(set(result), PAY_KEYS)
        self.assertEqual(result["section"], "payment")
        self.assertEqual(result["version"], cs.__version__)
        self.assertLessEqual(len(self.line.encode("utf-8")), 30000)
        self.assertNotIn("SENTINEL_PAY_31", self.line)
        self.assertNotIn("price_123", self.line)
        paths = set()
        for root, _, files in os.walk(self.repo):
            for f in files:
                paths.add(os.path.relpath(os.path.join(root, f), self.repo).replace(os.sep, "/"))

        def strings(obj, key=None):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield from strings(v, k)
            elif isinstance(obj, list):
                for v in obj:
                    yield from strings(v, key)
            elif isinstance(obj, str):
                yield key, obj
        for key, s in strings(result):
            self.assertTrue(s in cs.PAY_VOCABULARY or (key == "path" and s in paths), "%s=%r" % (key, s))

    def test_failure_envelope(self):
        """protects=a missing folder gives the fixed envelope, never a traceback;
        fails_when=the payment call prints anything else;
        no_claim=only the not-found case is tried here."""
        result, _, _ = run(self.parent, "nope", "--section", "payment")
        self.assertEqual(set(result), {"ok", "error", "hint", "partial"})
        self.assertFalse(result["ok"])


# ------------------------------------------------------------------- writers

class WriterTests(PayCase):
    def test_webhook_and_success_page_both_save_paid(self):
        """protects=the headline finding: paid status saved by the payment handler AND by a thank-you page;
        fails_when=either place is missing or labeled with the wrong kind;
        no_claim=a writer is a write call with a paid field near it, not a confirmed paid-state change."""
        self.w("package.json", NEXT_PKG)
        self.w("app/api/stripe/route.ts", UNVERIFIED_HOOK)
        self.w("app/success/page.tsx", SUCCESS_PAGE)
        got = self.writers(self.pay())
        self.assertIn(("app/api/stripe/route.ts", 5, "is_paid", "webhook"), got)
        self.assertIn(("app/success/page.tsx", 5, "is_paid", "success-page"), got)

    def test_kinds_page_browser_other(self):
        """protects=each writer says what kind of place it is;
        fails_when=a server page, a browser screen or a server file gets another kind;
        no_claim=kinds come from paths and markers, not from reading what runs."""
        self.w("package.json", VITE_SUPABASE_PKG)
        self.w("src/Upgrade.tsx", "import { createClient } from '@supabase/supabase-js'\nconst supabase = createClient(u, k)\n"
               "export const go = () => supabase.from('profiles').update({ plan: 'pro' })\n")
        self.w("server/billing.ts", "export async function mark(db, id) {\n  await db.user.update({\n    where: { id },\n    data: { isPro: true },\n  })\n}\n")
        self.w("pages/account.tsx", "export async function getServerSideProps() {\n  await db.update(users).set({ tier: 'gold' })\n}\n")
        got = self.writers(self.pay())
        self.assertIn(("src/Upgrade.tsx", 3, "plan", "browser"), got)
        self.assertIn(("server/billing.ts", 2, "is_pro", "other"), got)
        self.assertIn(("pages/account.tsx", 2, "tier", "page"), got)

    def test_status_counts_only_beside_payment_words(self):
        """protects=an order or task status is not paid state;
        fails_when=a plain status write is listed, or a subscription status write is missed;
        no_claim=a status field with an unusual name or value is missed."""
        self.w("lib/tasks.ts", "export const done = () => db.from('tasks').update({ status: 'done' })\n")
        self.w("lib/orders.ts", "export const ship = () => db.from('orders').update({ status: 'shipped' })\n")
        self.w("lib/subs.ts", "export const sync = (s) => db.from('profiles').update({\n  subscription_status: s.status,\n})\n")
        self.w("lib/pay.ts", "export const ok = () => db.from('accounts').update({ status: 'trialing' })\n")
        got = self.writers(self.pay())
        paths = {g[0] for g in got}
        self.assertNotIn("lib/tasks.ts", paths)
        self.assertNotIn("lib/orders.ts", paths)
        self.assertIn(("lib/subs.ts", 1, "subscription_status", "other"), got)
        self.assertIn(("lib/pay.ts", 1, "status", "other"), got)

    def test_field_of_the_next_statement_is_not_borrowed(self):
        """protects=a write is judged only by what its own call writes;
        fails_when=a status: 'done' write is listed because the next statement writes credits;
        no_claim=brackets inside strings can still end the window early (says less, never more)."""
        self.w("app/actions.ts", "'use server'\nexport async function a(id) {\n"
               "  await db.from('tasks').update({ status: 'done' }).eq('id', id)\n}\n"
               "export async function b(id) {\n  await db.from('profiles').update({ credits: 5 })\n}\n")
        self.assertEqual(self.writers(self.pay()), [("app/actions.ts", 6, "credits", "other")])

    def test_write_to_a_subscriptions_table(self):
        """protects=a writer that saves a whole subscription record (the common template layout) is found;
        fails_when=an upsert into a subscriptions table is missed;
        no_claim=tables with other names are missed."""
        self.w("utils/admin.ts", "export const up = (row) => supabaseAdmin\n  .from('subscriptions')\n  .upsert([row])\n")
        got = self.writers(self.pay())
        self.assertIn(("utils/admin.ts", 3, "subscriptions", "other"), got)

    def test_sql_update_set(self):
        """protects=SQL writes count;
        fails_when=UPDATE ... SET is_paid is missed;
        no_claim=SQL built from pieces is missed."""
        self.w("api/db.py", "def mark(cur, uid):\n    cur.execute(\"UPDATE users SET is_paid = TRUE WHERE id = %s\", (uid,))\n")
        got = self.writers(self.pay())
        self.assertIn(("api/db.py", 2, "is_paid", "other"), got)

    def test_negatives(self):
        """protects=comments, reads, payment-company calls and far-away fields are not writers;
        fails_when=any of them is listed;
        no_claim=noise in shapes not tried here is not measured."""
        self.w("lib/a.ts", "// await db.from('profiles').update({ is_paid: true })\n")
        self.w("lib/b.ts", "export const r = () => db.from('profiles').select('is_paid')\n")
        self.w("lib/c.ts", "await stripe.customers.update(id, {\n  metadata: { plan: 'pro' },\n})\n")
        self.w("lib/d.ts", "await db.from('profiles').update({ name })\n\n\n\n\nconst x = { is_paid: true }\n")
        self.w("lib/e.ts", "hash.update(data)\nconst plan = 'pro'\n")
        self.assertEqual(self.writers(self.pay()), [])


# ------------------------------------------------------------------- payment handlers

class WebhookTests(PayCase):
    def test_unverified_route(self):
        """protects=the handler with no signature check is listed as not-found;
        fails_when=it is missing or marked found;
        no_claim=checks done outside the files this run follows are not seen (that is what not-found means)."""
        self.w("app/api/stripe/route.ts", UNVERIFIED_HOOK.replace("import { supabaseAdmin } from '../../../lib/admin'\n", ""))
        self.assertEqual(self.hooks(self.pay()), {"app/api/stripe/route.ts": "not-found"})

    def test_verified_in_file(self):
        """protects=a handler that checks the signature itself is never a finding;
        fails_when=it is listed as not-found;
        no_claim=whether the check is correct is not judged."""
        self.w("app/api/webhooks/route.ts", VERIFIED_HOOK)
        self.assertEqual(self.hooks(self.pay()), {"app/api/webhooks/route.ts": "found"})

    def test_verified_in_a_relative_import(self):
        """protects=the common template layout (the check lives in lib/stripe) is not a false alarm;
        fails_when=a check one relative import away is not found;
        no_claim=checks two imports away are not followed."""
        self.w("lib/stripe.ts", "export function verify(body, sig) {\n  return stripe.webhooks.constructEvent(body, sig, secret)\n}\n")
        self.w("app/api/webhooks/route.ts", "import { verify } from '../../../lib/stripe'\n"
               "export async function POST(req) {\n  const event = verify(await req.text(), req.headers.get('stripe-signature'))\n"
               "  if (event.type === 'invoice.paid') {}\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"app/api/webhooks/route.ts": "found"})

    def test_python_construct_event(self):
        """protects=a Python handler that verifies is not a finding;
        fails_when=stripe.Webhook.construct_event is not seen;
        no_claim=other Python frameworks' entry points may be missed."""
        self.w("server/app.py", "from flask import Flask\napp = Flask(__name__)\n@app.route('/webhook', methods=['POST'])\n"
               "def hook():\n    event = stripe.Webhook.construct_event(request.data, sig, secret)\n"
               "    if event['type'] == 'checkout.session.completed':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"server/app.py": "found"})

    def test_hand_made_signature_check_counts(self):
        """protects=a hand-written signature check (an edge function without the Stripe library) is not a false alarm;
        fails_when=createHmac with timingSafeEqual is not counted as a check;
        no_claim=whether it is done right is not judged."""
        self.w("supabase/functions/stripe-webhook/index.ts",
               "Deno.serve(async (req) => {\n  const sig = req.headers.get('stripe-signature')\n"
               "  const mac = createHmac('sha256', secret)\n  if (!timingSafeEqual(a, b)) return new Response('no', { status: 400 })\n"
               "  if (event.type === 'checkout.session.completed') {}\n})\n")
        self.assertEqual(self.hooks(self.pay()), {"supabase/functions/stripe-webhook/index.ts": "found"})

    def test_edge_function_unverified(self):
        """protects=Supabase edge functions are payment handlers too (Lovable apps use them);
        fails_when=an edge function with an event name and no check is not listed;
        no_claim=other hosting folders are not tried here."""
        self.w("supabase/functions/stripe-webhook/index.ts",
               "Deno.serve(async (req) => {\n  const event = await req.json()\n"
               "  if (event.type === 'checkout.session.completed') {}\n})\n")
        self.assertEqual(self.hooks(self.pay()), {"supabase/functions/stripe-webhook/index.ts": "not-found"})

    def test_comment_only_check_is_not_found(self):
        """protects=a check that only appears in a comment does not count;
        fails_when=a commented-out constructEvent marks the handler found;
        no_claim=checks inside strings are not told apart."""
        self.w("app/api/stripe/route.ts", "export async function POST(req) {\n"
               "  // const event = stripe.webhooks.constructEvent(body, sig, secret)\n"
               "  const event = await req.json()\n  if (event.type === 'invoice.paid') {}\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"app/api/stripe/route.ts": "not-found"})

    def test_past_the_file_cap_is_unresolved(self):
        """protects=a handler whose imports reach more files than are followed is never called missing;
        fails_when=a handler importing 25 files, none checking, is listed as not-found;
        no_claim=the cap (20 files) trades verdicts for time; past it the report says nothing."""
        for i in range(25):
            self.w("lib/m%d.ts" % i, "export const x%d = 1\n" % i)
        imports = "".join("import { x%d } from '../../../lib/m%d'\n" % (i, i) for i in range(25))
        self.w("app/api/stripe/route.ts", imports + "export async function POST(req) {\n  if (e.type === 'invoice.paid') {}\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"app/api/stripe/route.ts": "unresolved"})

    def test_past_the_depth_limit_is_unresolved(self):
        """protects=a chain of imports longer than is followed is never called missing;
        fails_when=a check 4 levels down reads not-found;
        no_claim=3 levels are followed."""
        self.w("lib/a.ts", "import { b } from './b'\nexport const a = b\n")
        self.w("lib/b.ts", "import { c } from './c'\nexport const b = c\n")
        self.w("lib/c.ts", "import { d } from './d'\nexport const c = d\n")
        self.w("lib/d.ts", "export const d = (x) => stripe.webhooks.constructEvent(x, s, k)\n")
        self.w("app/api/stripe/route.ts", "import { a } from '../../../lib/a'\nexport async function POST(req) {\n"
               "  if (e.type === 'invoice.paid') {}\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"app/api/stripe/route.ts": "unresolved"})

    def test_handler_module_is_not_an_entry_point(self):
        """protects=a module that only switches on the event type is not listed as a handler;
        fails_when=lib/handlers.ts is listed;
        no_claim=entry points are found by place in the tree and server markers only."""
        self.w("lib/handlers.ts", "export function onEvent(event) {\n  switch (event.type) {\n    case 'invoice.paid': return 1\n  }\n}\n")
        self.assertEqual(self.hooks(self.pay()), {})


# ------------------------------------------------------------------- prices and browser writes

class PricePairTests(PayCase):
    def test_price_in_code_and_payment_company_id(self):
        """protects=a price written in the app next to a payment-company price id is pointed out;
        fails_when=both exist and price_pairs is empty;
        no_claim=whether they are the same plan is for the reader to confirm."""
        self.w("src/lib/plans.ts", "export const PRO_PRICE = 19\n")
        self.w("src/lib/checkout.ts", "export const go = () => create({ price_id: PRO })\n")
        got = self.pay()["price_pairs"]
        self.assertEqual(got["constants"], [{"path": "src/lib/plans.ts", "line": 1}])
        self.assertEqual(got["payment_ids"], [{"path": "src/lib/checkout.ts", "line": 1}])

    def test_no_pair_without_both(self):
        """protects=a price alone, or a price id alone, is not a pair;
        fails_when=price_pairs lists anything;
        no_claim=prices set only in the payment company's dashboard are not seen."""
        self.w("src/lib/plans.ts", "export const PRO_PRICE = 19\n")
        got = self.pay()["price_pairs"]
        self.assertEqual(got, {"constants": [], "payment_ids": []})


class ClientWriteTests(PayCase):
    def test_browser_saves_credits_and_total(self):
        """protects=gate d3b: screens that save credits or a total straight to the database are listed;
        fails_when=either write is missing;
        no_claim=listed, not confirmed: the database may still refuse the write."""
        self.w("package.json", VITE_SUPABASE_PKG)
        self.w("src/Buy.tsx", "import { createClient } from '@supabase/supabase-js'\nconst supabase = createClient(u, k)\n"
               "export async function buy(n) {\n  await supabase.from('profiles').update({ credits: me.credits + n })\n"
               "  await supabase.from('orders').insert({\n    total: price * qty,\n  })\n}\n")
        got = self.client(self.pay())
        self.assertIn(("src/Buy.tsx", 4, "credits"), got)
        self.assertIn(("src/Buy.tsx", 5, "total"), got)

    def test_server_write_of_the_same_field_is_not_a_browser_write(self):
        """protects=a server-only write of the same column is not listed as a browser write;
        fails_when=a route file or a 'use server' file is listed;
        no_claim=server code is told apart by path and markers."""
        self.w("package.json", NEXT_PKG)
        self.w("app/api/credits/route.ts", "export async function POST() {\n  await supabase.from('profiles').update({ credits: 5 })\n}\n")
        self.w("app/actions.ts", "'use server'\nexport async function add() {\n  await supabase.from('profiles').update({ credits: 5 })\n}\n")
        self.assertEqual(self.client(self.pay()), [])


class LimitTests(PayCase):
    def test_output_cap_trims_and_says_so(self):
        """protects=the 30000-byte line cap, with output_trimmed said;
        fails_when=the line is longer or the trim is silent;
        no_claim=which entries are trimmed is the biggest-list-first rule."""
        for i in range(400):
            self.w("lib/w%03d_%s.ts" % (i, "x" * 120), "export const f = () => db.from('profiles').update({ is_paid: true })\n")
        result = self.pay()
        self.assertLessEqual(len(self.line.encode("utf-8")), 30000)
        self.assertEqual(result["totals"]["writers"]["listed"] + result["totals"]["writers"]["not_listed"], 400)
        self.assertLessEqual(result["totals"]["writers"]["listed"], 25)

    def test_trim_loop_cuts_the_line_and_says_so(self):
        """protects=when the line would pass the byte cap, entries are cut and output_trimmed is said;
        fails_when=the trim body is removed or silent;
        no_claim=the cap is lowered in-process so the loop is reached; the real cap is 30000 bytes."""
        import contextlib
        import io
        for i in range(30):
            self.w("lib/w%02d_%s.ts" % (i, "x" * 150), "export const f = () => db.from('profiles').update({ is_paid: true })\n")
        old = cs.MAX_OUTPUT_BYTES
        cs.MAX_OUTPUT_BYTES = 3000
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                cs.main(["--repo", self.repo, "--section", "payment"])
        finally:
            cs.MAX_OUTPUT_BYTES = old
        line = out.getvalue().strip()
        result = json.loads(line)
        self.assertLessEqual(len(line.encode("utf-8")), 3000)
        self.assertIn("output_trimmed", result["partial_reasons"])
        self.assertGreater(result["totals"]["writers"]["not_listed"], 5)

    def test_long_lines_of_dots_stay_fast(self):
        """protects=the time limit on hostile Python files (a line of dots once took seconds per file);
        fails_when=a 400 KB file of `from ....` lines takes more than 3 s (it took about 6 s before the fix);
        no_claim=one machine's timing; the margin is wide."""
        import time
        self.w("evil.py", ("from " + "." * 2000 + "x\n") * 200)
        t = time.monotonic()
        self.pay()
        self.assertLess(time.monotonic() - t, 3.0)

    def test_stopped_walk_with_nothing_is_not_determined(self):
        """protects=a walk that stopped early never reads as 'nothing found';
        fails_when=coverage says complete;
        no_claim=the file limit stands in for every early stop."""
        for i in range(3):
            self.w("lib/f%d.ts" % i, "export const a = 1\n")
        result = self.pay("--max-files", "1")
        self.assertEqual(result["coverage"], "not_determined")
        self.assertTrue(result["partial"])


# ------------------------------------------------------------------- review round 1 (0.5.0)
#
# Each case below is a layout a reviewer showed. The rule they protect: "no signature check found" is said
# only when every local file the handler depends on was followed and none checks. Anything not followed
# (an import this run cannot place, a cap) makes the verdict unresolved, which the report never prints.

HOOK_BODY = (
    "export async function POST(req) {\n"
    "  const event = await verify(await req.text(), req.headers.get('stripe-signature'))\n"
    "  if (event.type === 'invoice.paid') {}\n"
    "  return new Response('ok')\n"
    "}\n")
VERIFY_LIB = ("import Stripe from 'stripe'\nconst stripe = new Stripe(k)\n"
              "export function verify(body, sig) {\n  return stripe.webhooks.constructEvent(body, sig, s)\n}\n")
TSCONFIG_ROOT = json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"], "@lib/*": ["lib/*"]}}})


class ResolveTests(PayCase):
    def hook_with(self, import_line, files):
        self.w("package.json", NEXT_PKG)
        for rel, text in files.items():
            self.w(rel, text)
        self.w("app/api/stripe/route.ts", import_line + "\n" + HOOK_BODY)
        return self.hooks(self.pay())["app/api/stripe/route.ts"]

    def test_python_absolute_import_check_is_found(self):
        """protects=the FastAPI layout (absolute import of a local module that checks) is not a false alarm;
        fails_when=`from app.deps import stripe_event` is not followed and the handler reads not-found;
        no_claim=only modules inside the repo are followed."""
        self.w("app/__init__.py", "")
        self.w("app/deps.py", "import stripe\nasync def stripe_event(request):\n"
               "    return stripe.Webhook.construct_event(await request.body(), sig, SECRET)\n")
        self.w("app/routers/billing.py", "from fastapi import APIRouter, Depends\nfrom app.deps import stripe_event\n"
               "router = APIRouter()\n@router.post('/webhooks/stripe')\nasync def webhook(event=Depends(stripe_event)):\n"
               "    if event['type'] == 'checkout.session.completed':\n        pass\n")
        self.w("app/main.py", "from fastapi import FastAPI\nfrom app.routers import billing\napp = FastAPI()\n"
               "app.include_router(billing.router)\n")
        self.assertEqual(self.hooks(self.pay()), {"app/routers/billing.py": "found"})

    def test_python_absolute_import_from_the_handler_folder(self):
        """protects=a module next to the handler, imported by absolute name (`from billing.verify import`), is followed;
        fails_when=it reads not-found;
        no_claim=the repo root, src/ and the handler's own folders are the places tried."""
        self.w("svc/billing/__init__.py", "")
        self.w("svc/billing/verify.py", "import stripe\ndef verify(p, s):\n    return stripe.Webhook.construct_event(p, s, K)\n")
        self.w("svc/main.py", "from fastapi import FastAPI, Request\nfrom billing.verify import verify\napp = FastAPI()\n"
               "@app.post('/stripe/webhook')\nasync def hook(request: Request):\n"
               "    event = verify(await request.body(), request.headers.get('stripe-signature'))\n"
               "    if event['type'] == 'checkout.session.completed':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"svc/main.py": "found"})

    def test_python_parenthesized_relative_import(self):
        """protects=`from .x import (` over several lines is followed;
        fails_when=it reads not-found;
        no_claim=star imports are followed like any other."""
        self.w("srv/verify.py", "import stripe\ndef check(p, s):\n    return stripe.Webhook.construct_event(p, s, K)\n")
        self.w("srv/main.py", "from flask import Flask, request\nfrom .verify import (\n    check,\n)\napp = Flask(__name__)\n"
               "@app.route('/hook', methods=['POST'])\ndef hook():\n    event = check(request.data, sig)\n"
               "    if event['type'] == 'invoice.paid':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"srv/main.py": "found"})

    def test_python_relative_import_from_package(self):
        """protects=`from . import verify` resolves to the module next to the handler;
        fails_when=the dots count one folder too many or too few;
        no_claim=deeper dot chains follow the same rule."""
        self.w("srv/verify.py", "import stripe\ndef check(p, s):\n    return stripe.Webhook.construct_event(p, s, K)\n")
        self.w("srv/main.py", "from flask import Flask, request\nfrom . import verify\napp = Flask(__name__)\n"
               "@app.route('/hook', methods=['POST'])\ndef hook():\n    event = verify.check(request.data, sig)\n"
               "    if event['type'] == 'invoice.paid':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"srv/main.py": "found"})

    def test_python_local_module_that_cannot_be_placed_is_unresolved(self):
        """protects=a local package import this run cannot place is never called missing;
        fails_when=it reads not-found;
        no_claim=packages installed from outside the repo are not followed (they are not the app's code)."""
        self.w("billing/__init__.py", "")
        self.w("main.py", "from flask import Flask\nfrom billing.verify import verify\napp = Flask(__name__)\n"
               "@app.route('/hook', methods=['POST'])\ndef hook():\n"
               "    if event['type'] == 'invoice.paid':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"main.py": "unresolved"})

    def test_bare_base_url_import(self):
        """protects=`import ... from 'lib/stripe'` is followed when the app's tsconfig sets baseUrl;
        fails_when=it reads not-found;
        no_claim=only the app's own tsconfig/jsconfig decides where a bare import points."""
        self.w("tsconfig.json", TSCONFIG_ROOT)
        self.assertEqual(self.hook_with("import { verify } from 'lib/stripe'", {"lib/stripe.ts": VERIFY_LIB}), "found")

    def test_scoped_alias_that_is_not_a_dependency(self):
        """protects=`@lib/stripe` (a tsconfig path, not an installed package) is followed;
        fails_when=it reads not-found;
        no_claim=the alias folder comes from tsconfig paths, never from its name."""
        self.w("tsconfig.json", TSCONFIG_ROOT)
        self.assertEqual(self.hook_with("import { verify } from '@lib/stripe'", {"lib/stripe.ts": VERIFY_LIB}), "found")

    def test_at_slash_alias_is_followed(self):
        """protects=`@/lib/x` is followed to the folder tsconfig paths name;
        fails_when=a check behind @/ reads not-found;
        no_claim=one config per folder, the nearest one above the importing file."""
        self.w("tsconfig.json", json.dumps({"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}))
        self.assertEqual(self.hook_with("import { verify } from '@/lib/stripe'", {"src/lib/stripe.ts": VERIFY_LIB}), "found")

    def test_alias_to_a_file_without_a_check_is_not_found(self):
        """protects=the paywall case still reads not-found when the alias target was followed and has no check;
        fails_when=a followed alias makes every handler unresolved;
        no_claim=the target is the file the alias names, by the same rule as above."""
        self.w("tsconfig.json", TSCONFIG_ROOT)
        self.assertEqual(self.hook_with("import { db } from '@/lib/db'", {"lib/db.ts": "export const db = 1\n"}), "not-found")

    def test_js_extension_maps_to_ts(self):
        """protects=`./verify.js` written for a .ts file (ESM style) is followed;
        fails_when=it reads unresolved or not-found;
        no_claim=.mjs and .cjs follow the same rule."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/verify.js'",
                                        {"lib/verify.ts": VERIFY_LIB}), "found")

    def test_two_hops_of_relative_imports(self):
        """protects=route -> handler module -> verifier is followed;
        fails_when=the second hop is not read and it reads not-found;
        no_claim=depth is capped (3); past it the verdict is unresolved."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/hook'", {
            "lib/hook.ts": "import { verify as v } from './stripe'\nexport const verify = v\n",
            "lib/stripe.ts": VERIFY_LIB}), "found")

    def test_import_this_run_did_not_read_is_unresolved(self):
        """protects=a handler that imports a file this run did not read is never called missing;
        fails_when=removing the guard turns it into not-found;
        no_claim=the reason (missing, too big, generated) is not told apart."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/missing'", {}), "unresolved")

    def test_package_imports_are_not_gaps(self):
        """protects=imports of installed packages and node built-ins do not make a plain handler unresolved;
        fails_when=a handler importing only 'stripe', 'next/server' and 'crypto' reads anything but not-found;
        no_claim=a package from the repo's own workspaces is treated as unresolved."""
        self.assertEqual(self.hook_with("import Stripe from 'stripe'\nimport { NextResponse } from 'next/server'\n"
                                        "import crypto from 'node:crypto'\nimport { join } from 'path'", {}), "not-found")

    def test_unknown_package_is_unresolved(self):
        """protects=a bare import that is neither a listed package nor a file this run can place is not ignored;
        fails_when=it reads not-found;
        no_claim=listed packages are trusted not to be the app's own code."""
        self.assertEqual(self.hook_with("import { verify } from 'billing-kit/verify'", {}), "unresolved")

    def test_workspace_package_is_unresolved(self):
        """protects=a monorepo package (`workspace:*`, or a name another package.json in the repo has) is not
        treated as outside code;
        fails_when=it reads not-found;
        no_claim=the workspace package is not followed."""
        self.w("packages/billing/package.json", json.dumps({"name": "@acme/billing"}))
        self.w("packages/billing/index.ts", VERIFY_LIB)
        self.assertEqual(self.hook_with("import { verify } from '@acme/billing'", {}), "unresolved")

    def test_express_mount_checks_before_the_router(self):
        """protects=Express apps that check in middleware mounted in app.js before the router are not a false alarm;
        fails_when=the route file reads not-found or found (a check beside the mount cannot be tied to this route);
        no_claim=files that import the handler are followed up to 3 levels, plus what they import."""
        self.w("package.json", json.dumps({"name": "api", "dependencies": {"express": "4.19.0", "stripe": "16.0.0"}}))
        self.w("app.js", "const express = require('express');\nconst verifyStripe = require('./middleware/stripeWebhook');\n"
               "const webhookRouter = require('./routes/webhook');\nconst app = express();\n"
               "app.use('/api/webhook', express.raw({ type: 'application/json' }), verifyStripe, webhookRouter);\napp.listen(3000);\n")
        self.w("middleware/stripeWebhook.js", "const stripe = require('stripe')(k);\nmodule.exports = function (req, res, next) {\n"
               "  req.event = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], s); next();\n};\n")
        self.w("routes/webhook.js", "const express = require('express');\nconst router = express.Router();\n"
               "router.post('/', async (req, res) => {\n  if (req.event.type === 'checkout.session.completed') {}\n"
               "  res.json({ received: true });\n});\nmodule.exports = router;\n")
        self.assertEqual(self.hooks(self.pay()), {"routes/webhook.js": "unresolved"})

    def test_walk_that_stopped_early_is_unresolved(self):
        """protects=when the walk stops before reading every file, a handler is never called missing;
        fails_when=a handler read before the stop, with the check in a file the walk never reached, reads not-found;
        no_claim=the file limit stands in for every early stop."""
        self.w("package.json", json.dumps({"name": "api", "dependencies": {"express": "4.19.0"}}))
        self.w("hook.js", "const express = require('express');\nconst app = express();\n"
               "app.post('/webhook', (req, res) => {\n  if (req.body.type === 'invoice.paid') {}\n  res.sendStatus(200);\n});\n"
               "app.listen(3000);\n")
        self.w("zz/mount.js", "require('../hook');\nconst e = stripe.webhooks.constructEvent(b, s, k);\n")
        self.assertEqual(self.hooks(self.pay("--max-files", "1")), {"hook.js": "unresolved"})


class VerifyRuleTests(PayCase):
    def one(self, body):
        self.w("package.json", NEXT_PKG)
        self.w("app/api/stripe/route.ts", body)
        return self.hooks(self.pay())["app/api/stripe/route.ts"]

    def test_unrelated_hmac_is_not_a_check(self):
        """protects=an HMAC made for something else (a log id) does not hide a missing check;
        fails_when=createHmac alone counts as a check;
        no_claim=a hand-made check counts when a signature is compared."""
        self.assertEqual(self.one(
            "import { createHmac } from 'crypto'\nexport async function POST(req) {\n  const event = await req.json()\n"
            "  const logId = createHmac('sha256', 'k').update(event.id).digest('hex')\n"
            "  if (event.type === 'checkout.session.completed') {}\n}\n"), "not-found")

    def test_hand_made_hmac_compared_with_the_signature_counts(self):
        """protects=a hand-made check that compares the HMAC with the signature header is a check;
        fails_when=it reads not-found;
        no_claim=a plain === comparison counts; whether it is timing-safe is not judged."""
        self.assertEqual(self.one(
            "import { createHmac } from 'crypto'\nexport async function POST(req) {\n  const body = await req.text()\n"
            "  const sig = req.headers.get('stripe-signature')\n"
            "  const expected = createHmac('sha256', secret).update(body).digest('hex')\n"
            "  if (expected !== sig) return new Response('bad', { status: 400 })\n"
            "  const event = JSON.parse(body)\n  if (event.type === 'invoice.paid') {}\n}\n"), "found")

    def test_check_inside_a_block_comment_is_not_found(self):
        """protects=a check that was switched off with /* ... */ does not count;
        fails_when=a line inside a block comment counts;
        no_claim=Python strings used as comments are not tracked."""
        self.assertEqual(self.one(
            "export async function POST(req) {\n  /*\n  const event = stripe.webhooks.constructEvent(body, sig, secret)\n"
            "  */\n  const event = await req.json()\n  if (event.type === 'invoice.paid') {}\n}\n"), "not-found")

    def test_block_comment_markers_in_strings_do_not_hide_code(self):
        """protects=a '/*' inside a string (a glob) does not turn the rest of the file into a comment;
        fails_when=the check after it is missed;
        no_claim=template strings over several lines are tracked approximately."""
        self.assertEqual(self.one(
            "const glob = 'src/**/*.ts'\nexport async function POST(req) {\n"
            "  const event = stripe.webhooks.constructEvent(await req.text(), req.headers.get('stripe-signature'), s)\n"
            "  if (event.type === 'invoice.paid') {}\n}\n"), "found")

    def test_verify_header_counts(self):
        """protects=stripe.webhooks.signature.verifyHeader is a check;
        fails_when=it reads not-found;
        no_claim=Python verify_header follows the same rule."""
        self.assertEqual(self.one(
            "export async function POST(req) {\n  const body = await req.text()\n"
            "  stripe.webhooks.signature.verifyHeader(body, req.headers.get('stripe-signature'), secret)\n"
            "  const event = JSON.parse(body)\n  if (event.type === 'invoice.paid') {}\n}\n"), "found")

    def test_payment_company_sdk_unmarshal_counts(self):
        """protects=another payment company's checked parse (paddle.webhooks.unmarshal) is a check;
        fails_when=it reads not-found;
        no_claim=only these named calls are known."""
        self.assertEqual(self.one(
            "export async function POST(req) {\n  const body = await req.text()\n"
            "  const event = await paddle.webhooks.unmarshal(body, secret, req.headers.get('paddle-signature'))\n"
            "  if (body.includes('\"invoice.paid\"')) {}\n}\n"), "found")


class Round2Tests(PayCase):
    """0.5.0 review round 2: every case the rebuilt check must get right. not-found needs a certain chain;
    anything this run cannot place for sure is unresolved."""

    def hook_with(self, import_line, files, pkg=NEXT_PKG):
        self.w("package.json", pkg)
        for rel, text in files.items():
            self.w(rel, text)
        self.w("app/api/stripe/route.ts", import_line + "\n" + HOOK_BODY)
        return self.hooks(self.pay())["app/api/stripe/route.ts"]

    def one(self, body):
        self.w("package.json", NEXT_PKG)
        self.w("app/api/stripe/route.ts", body)
        return self.hooks(self.pay())["app/api/stripe/route.ts"]

    # dotted names, assets, several candidates
    def test_dotted_file_name_is_code(self):
        """protects=`./webhook.utils` is a code file, not a stylesheet;
        fails_when=a check in lib/webhook.utils.ts reads not-found;
        no_claim=only the fixed asset list is treated as non-code."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/webhook.utils'",
                                        {"lib/webhook.utils.ts": VERIFY_LIB}), "found")

    def test_dotted_edge_file_name_is_code(self):
        """protects=`../lib/stripe.edge` is followed to stripe.edge.ts;
        fails_when=it reads not-found;
        no_claim=as above."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/stripe.edge'",
                                        {"lib/stripe.edge.ts": VERIFY_LIB}), "found")

    def test_unknown_extension_with_no_file_is_unresolved(self):
        """protects=an import with an odd extension that names no file this run read is never treated as outside code;
        fails_when=it reads not-found;
        no_claim=stylesheets, images and data files on the asset list stay outside."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/thing.weird'", {}), "unresolved")

    def test_asset_imports_are_not_gaps(self):
        """protects=a stylesheet or JSON import does not make a plain handler unresolved;
        fails_when=it reads anything but not-found;
        no_claim=the asset list is fixed."""
        self.assertEqual(self.hook_with("import '../../../styles/x.css'\nimport plans from '../../../data/plans.json'",
                                        {"data/plans.json": "{}\n"}), "not-found")

    def test_two_candidate_files_is_unresolved(self):
        """protects=when an import could name two files this run read, the verdict is not guessed;
        fails_when=it picks one and reads not-found;
        no_claim=which file a bundler would pick is not modelled."""
        self.assertEqual(self.hook_with("import { verify } from '../../../lib/verify'", {
            "lib/verify.ts": "export const verify = 1\n", "lib/verify/index.ts": "export const verify = 2\n"}), "unresolved")

    # the app's own path settings
    def test_tsconfig_paths_beat_the_root_folder(self):
        """protects=`@/*` -> `./src/*` follows src/lib/verify.ts, not an unrelated lib/verify.ts at the root;
        fails_when=the root file wins and it reads not-found;
        no_claim=paths patterns with one `*` are read."""
        self.w("tsconfig.json", json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./src/*"]}}}))
        self.assertEqual(self.hook_with("import { verify } from '@/lib/verify'", {
            "lib/verify.ts": "export const verify = (x) => x\n", "src/lib/verify.ts": VERIFY_LIB}), "found")

    def test_alias_without_a_config_is_unresolved(self):
        """protects=with no tsconfig or jsconfig, `@/x` is not guessed;
        fails_when=a guessed folder with no check reads not-found;
        no_claim=bundler aliases (vite, webpack) are not read."""
        self.assertEqual(self.hook_with("import { db } from '@/lib/db'", {"lib/db.ts": "export const db = 1\n"}), "unresolved")

    def test_config_with_comments_and_trailing_commas_is_read(self):
        """protects=tsconfig files are JSON with comments; they still count;
        fails_when=a commented config is ignored and the alias reads unresolved;
        no_claim=only // and /* */ comments and trailing commas are tolerated."""
        self.w("tsconfig.json", '{\n  // paths\n  "compilerOptions": {\n    /* alias */ "paths": {"@/*": ["./src/*",],},\n  },\n}\n')
        self.assertEqual(self.hook_with("import { verify } from '@/lib/verify'", {"src/lib/verify.ts": VERIFY_LIB}), "found")

    def test_config_extends_a_local_file(self):
        """protects=paths set in a local base config (`extends: ./tsconfig.base.json`) are used;
        fails_when=it reads unresolved or not-found;
        no_claim=up to 5 local extends are followed."""
        self.w("tsconfig.json", json.dumps({"extends": "./tsconfig.base.json"}))
        self.w("tsconfig.base.json", json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}))
        self.assertEqual(self.hook_with("import { verify } from '@/lib/verify'", {"src/lib/verify.ts": VERIFY_LIB}), "found")

    def test_config_extending_a_package_is_unresolved(self):
        """protects=settings that may come from an installed base config are not guessed;
        fails_when=the alias is resolved anyway and reads not-found;
        no_claim=a key set in the app's own file still wins over the package's."""
        self.w("tsconfig.json", json.dumps({"extends": "@tsconfig/next/tsconfig.json",
                                            "compilerOptions": {"paths": {"@/*": ["./*"]}}}))
        self.assertEqual(self.hook_with("import { db } from '@/lib/db'", {"lib/db.ts": "export const db = 1\n"}), "unresolved")

    def test_broken_config_is_unresolved(self):
        """protects=a config this run cannot parse is unknown, not empty;
        fails_when=the alias reads not-found;
        no_claim=why it does not parse is not reported."""
        self.w("tsconfig.json", '{"compilerOptions": {"paths": ')
        self.assertEqual(self.hook_with("import { db } from '@/lib/db'", {"lib/db.ts": "export const db = 1\n"}), "unresolved")

    def test_local_folder_named_like_a_node_builtin(self):
        """protects=`util/stripe` under baseUrl `src` is the app's file, not Node's util;
        fails_when=it is treated as a package and reads not-found;
        no_claim=baseUrl is tried before packages, as TypeScript does."""
        self.w("tsconfig.json", json.dumps({"compilerOptions": {"baseUrl": "src"}}))
        self.assertEqual(self.hook_with("import { verify } from 'util/stripe'", {"src/util/stripe.ts": VERIFY_LIB}), "found")

    # comments that may hide code, backticks
    def test_regex_literal_that_looks_like_a_comment_is_unresolved(self):
        """protects=`/[/*]/` above the check does not hide it and produce a false alarm;
        fails_when=it reads not-found;
        no_claim=regex literals are not parsed; a block comment opened after code makes the file not determined."""
        self.assertEqual(self.one(
            "const SLASHES = /[/*]/\nexport async function POST(req) {\n"
            "  const event = stripe.webhooks.constructEvent(await req.text(), req.headers.get('stripe-signature'), s)\n"
            "  if (event.type === 'invoice.paid') {}\n}\n"), "unresolved")

    def test_line_comment_cut_after_code_holding_a_check_is_unresolved(self):
        """protects=a `//` inside a regex on the same line as the check does not hide it;
        fails_when=it reads not-found;
        no_claim=a trailing comment without a check word stays a comment."""
        self.assertEqual(self.one(
            "export async function POST(req) {\n  const body = await req.text()\n"
            "  const p = body.replace(/\\/\\//g, '/'); const event = stripe.webhooks.constructEvent(body, req.headers.get('stripe-signature'), s)\n"
            "  if (event.type === 'invoice.paid') {}\n}\n"), "unresolved")

    def test_plain_trailing_comment_stays_certain(self):
        """protects=ordinary trailing comments do not turn every handler unresolved;
        fails_when=a handler with `// parse the body` reads unresolved;
        no_claim=only comments whose text holds a check word are doubted."""
        self.assertEqual(self.one(
            "export async function POST(req) {\n  const event = await req.json() // parse the body\n"
            "  if (event.type === 'invoice.paid') {} /* paid */\n}\n"), "not-found")

    def test_backtick_import_is_unresolved(self):
        """protects=an import written with backticks is not silently skipped;
        fails_when=it reads not-found;
        no_claim=backtick paths are never followed."""
        self.assertEqual(self.hook_with("const { verify } = await import(`../../../lib/stripe-verify`)",
                                        {"lib/stripe-verify.ts": VERIFY_LIB}), "unresolved")

    # importers
    def test_check_beside_the_mount_is_unresolved(self):
        """protects=an Express app whose other route checks does not lend that check to the webhook route;
        fails_when=routes/webhook.js reads found through app.js;
        no_claim=which route a check guards is not worked out, so this is not determined."""
        self.w("package.json", json.dumps({"name": "api", "dependencies": {"express": "4.19.0", "stripe": "16.0.0"}}))
        self.w("app.js", "const express = require('express');\nconst webhook = require('./routes/webhook');\n"
               "const other = require('./routes/other');\nconst app = express();\napp.use('/webhook', webhook);\n"
               "app.use('/other', other);\napp.listen(3000);\n")
        self.w("routes/other.js", "const router = require('express').Router();\nrouter.post('/', (req, res) => {\n"
               "  const e = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], s);\n  res.end();\n});\n"
               "module.exports = router;\n")
        self.w("routes/webhook.js", "const express = require('express');\nconst router = express.Router();\n"
               "router.post('/', async (req, res) => {\n  if (req.body.type === 'checkout.session.completed') {}\n"
               "  res.json({ received: true });\n});\nmodule.exports = router;\n")
        self.assertEqual(self.hooks(self.pay())["routes/webhook.js"], "unresolved")

    def test_importer_without_any_check_keeps_not_found(self):
        """protects=a mounted router with no check anywhere is still a finding;
        fails_when=it reads unresolved;
        no_claim=as above."""
        self.w("package.json", json.dumps({"name": "api", "dependencies": {"express": "4.19.0"}}))
        self.w("app.js", "const express = require('express');\nconst webhook = require('./routes/webhook');\n"
               "const app = express();\napp.use('/webhook', webhook);\napp.listen(3000);\n")
        self.w("routes/webhook.js", "const express = require('express');\nconst router = express.Router();\n"
               "router.post('/', async (req, res) => {\n  if (req.body.type === 'checkout.session.completed') {}\n"
               "  res.json({ received: true });\n});\nmodule.exports = router;\n")
        self.assertEqual(self.hooks(self.pay())["routes/webhook.js"], "not-found")

    # hand-made checks
    def test_hmac_compared_under_another_name_counts(self):
        """protects=a hand-made check whose names hold no "sig" is still a check;
        fails_when=`digest !== header` reads not-found;
        no_claim=the HMAC result must be compared, or passed to an equal/compare/verify call."""
        self.assertEqual(self.one(
            "import { createHmac } from 'crypto'\nexport async function POST(req) {\n  const body = await req.text()\n"
            "  const header = req.headers.get('x-payment-check')\n"
            "  const digest = createHmac('sha256', secret).update(body).digest('hex')\n"
            "  if (digest !== header) return new Response('bad', { status: 400 })\n"
            "  const event = JSON.parse(body)\n  if (event.type === 'invoice.paid') {}\n}\n"), "found")

    def test_hmac_passed_to_a_compare_call_counts(self):
        """protects=`safeEqual(digest, header)` is a check;
        fails_when=it reads not-found;
        no_claim=call names holding equal, compare or verify count."""
        self.assertEqual(self.one(
            "import { createHmac } from 'crypto'\nexport async function POST(req) {\n  const body = await req.text()\n"
            "  const digest = createHmac('sha256', secret).update(body).digest('hex')\n"
            "  if (!safeEqual(digest, req.headers.get('x-check'))) return new Response('bad', { status: 400 })\n"
            "  const event = JSON.parse(body)\n  if (event.type === 'invoice.paid') {}\n}\n"), "found")

    # python
    def test_python_from_package_import_follows_every_name(self):
        """protects=`from billing import a, b` follows billing/b.py too, not only billing/__init__.py;
        fails_when=a check in b.py reads not-found;
        no_claim=names that are functions, not modules, are simply not files."""
        self.w("billing/__init__.py", "")
        self.w("billing/a.py", "X = 1\n")
        self.w("billing/b.py", "import stripe\ndef check(p, s):\n    return stripe.Webhook.construct_event(p, s, K)\n")
        self.w("main.py", "from flask import Flask, request\nfrom billing import a, b\napp = Flask(__name__)\n"
               "@app.route('/hook', methods=['POST'])\ndef hook():\n    event = b.check(request.data, sig)\n"
               "    if event['type'] == 'invoice.paid':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"main.py": "found"})

    def test_python_module_in_two_places_is_unresolved(self):
        """protects=when `billing.verify` exists under two folders, the verdict is not guessed;
        fails_when=one is picked and it reads not-found;
        no_claim=sys.path order is not modelled."""
        for base in ("svc/", ""):
            self.w(base + "billing/__init__.py", "")
            self.w(base + "billing/verify.py", "def verify(p, s):\n    return p\n")
        self.w("svc/main.py", "from flask import Flask, request\nfrom billing.verify import verify\napp = Flask(__name__)\n"
               "@app.route('/hook', methods=['POST'])\ndef hook():\n    event = verify(request.data, sig)\n"
               "    if event['type'] == 'invoice.paid':\n        pass\n")
        self.assertEqual(self.hooks(self.pay()), {"svc/main.py": "unresolved"})


class LateTests(PayCase):
    """The short budget after the walk running out part-way never leaves a not-found behind."""

    def in_process(self, late_in):
        import contextlib
        import io
        real = cs._late

        def fake(state):
            if sys._getframe(1).f_code.co_name == late_in:
                state.reason("deadline_hit")
                return True
            return real(state)
        cs._late = fake
        cwd = os.getcwd()
        out = io.StringIO()
        try:
            os.chdir(self.parent)
            with contextlib.redirect_stdout(out):
                cs.main(["--repo", "app", "--section", "payment"])
        finally:
            os.chdir(cwd)
            cs._late = real
        return json.loads(out.getvalue().strip().split("\n")[0])

    def test_late_while_mapping_importers_is_unresolved(self):
        """protects=a partial map of importers never yields not-found;
        fails_when=a handler reads not-found after _late fired in importers();
        no_claim=the timer is forced in-process."""
        self.w("package.json", NEXT_PKG)
        self.w("lib/a.ts", "import { b } from './b'\nexport const a = b\n")
        self.w("lib/b.ts", "export const b = 1\n")
        self.w("app/api/stripe/route.ts", UNVERIFIED_HOOK.replace("import { supabaseAdmin } from '../../../lib/admin'\n", ""))
        self.assertEqual(self.hooks(self.in_process("importers")), {"app/api/stripe/route.ts": "unresolved"})

    def test_late_while_following_imports_is_unresolved(self):
        """protects=a walk of imports cut short by the timer never yields not-found;
        fails_when=_closure ignores _late;
        no_claim=as above."""
        self.w("package.json", NEXT_PKG)
        self.w("lib/a.ts", "export const a = 1\n")
        self.w("app/api/stripe/route.ts", "import { a } from '../../../lib/a'\n" + HOOK_BODY)
        self.assertEqual(self.hooks(self.in_process("_closure")), {"app/api/stripe/route.ts": "unresolved"})


class EntryPointTests(PayCase):
    def test_shared_folder_of_edge_functions_is_not_an_entry_point(self):
        """protects=supabase/functions/_shared helpers are never listed as payment handlers;
        fails_when=a _shared module with an event name is listed;
        no_claim=the function that imports it is judged on its own files."""
        self.w("supabase/functions/_shared/events.ts", "export default async function handle(event) {\n"
               "  switch (event.type) { case 'checkout.session.completed': break }\n}\n")
        self.w("supabase/functions/stripe-webhook/index.ts",
               "import Stripe from 'https://esm.sh/stripe@14'\nimport { handle } from '../_shared/events.ts'\n"
               "Deno.serve(async (req) => {\n  const event = await stripe.webhooks.constructEventAsync(await req.text(), "
               "req.headers.get('stripe-signature'), s)\n  await handle(event)\n  return new Response('ok')\n})\n")
        self.assertEqual(self.hooks(self.pay()), {"supabase/functions/stripe-webhook/index.ts": "found"})

    def test_helper_under_top_level_api_is_not_an_entry_point(self):
        """protects=a helper in api/lib/ with no exported handler is not listed;
        fails_when=it is listed;
        no_claim=folders and files starting with _ are skipped too, as Vercel does."""
        self.w("api/lib/stripe-events.js", "export function onEvent(event) {\n  if (event.type === 'invoice.paid') return 1\n}\n")
        self.w("api/_util.js", "export default function (event) {\n  if (event.type === 'invoice.paid') return 1\n}\n")
        self.assertEqual(self.hooks(self.pay()), {})

    def test_vercel_function_under_top_level_api_is_an_entry_point(self):
        """protects=api/stripe-webhook.ts (a Vercel function) is a payment handler;
        fails_when=it is not listed;
        no_claim=its export is what marks it."""
        self.w("api/stripe-webhook.ts", "export default async function handler(req, res) {\n  const event = req.body\n"
               "  if (event.type === 'checkout.session.completed') {}\n  res.status(200).end()\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"api/stripe-webhook.ts": "not-found"})

    def test_express_server_file_with_routes(self):
        """protects=an Express file with routes and an event name is a payment handler;
        fails_when=it is not listed;
        no_claim=a file with routes but no server marker is not."""
        self.w("package.json", json.dumps({"name": "api", "dependencies": {"express": "4.19.0"}}))
        self.w("server.js", "const express = require('express');\nconst app = express();\n"
               "app.post('/webhook', express.json(), (req, res) => {\n  if (req.body.type === 'invoice.paid') {}\n"
               "  res.sendStatus(200);\n});\napp.listen(3000);\n")
        self.w("lib/routes.js", "export const routes = [{ path: '/x' }]\nexport function f(e) {\n"
               "  if (e.type === 'invoice.paid') return 1\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"server.js": "not-found"})


class WriterRuleTests(PayCase):
    def writers_of(self, rel, text, pkg=NEXT_PKG):
        self.w("package.json", pkg)
        self.w(rel, text)
        return self.writers(self.pay())

    def test_pages_api_file_is_other_not_page(self):
        """protects=pages/api files are server code, not screens;
        fails_when=a pages/api writer reads 'page' or 'browser';
        no_claim=only the where word is checked here."""
        got = self.writers_of("pages/api/upgrade.ts", "export default async function h(req, res) {\n"
                              "  await prisma.user.update({ where: { id }, data: { is_paid: true } })\n}\n")
        self.assertEqual(got, [("pages/api/upgrade.ts", 2, "is_paid", "other")])

    def test_checkout_return_page_is_a_success_page(self):
        """protects=app/checkout/return/page.tsx (Stripe's embedded checkout return page) is a thank-you page;
        fails_when=it reads 'page';
        no_claim=other return paths are named by the success words."""
        got = self.writers_of("app/checkout/return/page.tsx", "export default async function R() {\n"
                              "  await db.from('profiles').update({ is_paid: true })\n}\n")
        self.assertEqual(got, [("app/checkout/return/page.tsx", 2, "is_paid", "success-page")])

    def test_assignment_two_lines_after_a_write_is_not_its_field(self):
        """protects=`plan = 'x'` on a later line is not a field of the write above it;
        fails_when=it is listed;
        no_claim=keyword arguments on the call's own line still count."""
        got = self.writers_of("lib/a.ts", "export async function f() {\n  await db.from('notes').update({\n    title,\n"
                              "  })\n  plan = 'pro'\n}\n")
        self.assertEqual(got, [])

    def test_active_status_without_payment_words_is_not_paid_state(self):
        """protects=status: 'active' on a project is not paid state;
        fails_when=it is listed;
        no_claim=status beside payment words, or a paid-only value, still counts."""
        self.assertEqual(self.writers_of("lib/p.ts", "await supabase.from('projects').update({ status: 'active' }).eq('id', id)\n"), [])

    def test_plan_without_payment_words_is_not_paid_state(self):
        """protects=a trip's plan is not a paid plan;
        fails_when=it is listed;
        no_claim=plan beside payment words or a plan name ('pro', 'free') still counts."""
        self.assertEqual(self.writers_of("lib/t.ts", "await supabase.from('trips').update({ plan: itinerary }).eq('id', id)\n"), [])

    def test_plan_with_a_plan_name_counts(self):
        """protects=plan: 'pro' is paid state;
        fails_when=it is not listed;
        no_claim=plan names are a fixed list."""
        got = self.writers_of("lib/u.ts", "await prisma.user.update({ where: { id }, data: { plan: 'pro' } })\n")
        self.assertEqual(got, [("lib/u.ts", 1, "plan", "other")])

    def test_table_named_lines_above_another_write_is_not_borrowed(self):
        """protects=a read of the subscriptions table on the line above does not make a profile write a paid writer;
        fails_when=it is listed as a subscriptions write;
        no_claim=the nearest table named before the call is the one used."""
        got = self.writers_of("lib/s.ts", "const { data } = await supabase.from('subscriptions').select('*')\n"
                              "await supabase.from('profiles').update({ full_name: name }).eq('id', id)\n")
        self.assertEqual(got, [])

    def test_stripe_word_earlier_on_the_line_does_not_hide_a_write(self):
        """protects=only a call made on the payment company's client is skipped;
        fails_when=`if (stripeSession.paid) await supabase...update(...)` is not listed;
        no_claim=a call whose receiver names stripe is still skipped."""
        got = self.writers_of("lib/w.ts", "if (stripeSession.paid) await supabase.from('profiles').update({ is_paid: true })\n"
                              "await stripe.subscriptions.update(id, { metadata: { plan: 'pro' } })\n")
        self.assertEqual(got, [("lib/w.ts", 1, "is_paid", "other")])


class ClientRuleTests(PayCase):
    def client_of(self, files):
        self.w("package.json", VITE_SUPABASE_PKG)
        for rel, text in files.items():
            self.w(rel, text)
        return self.client(self.pay())

    def test_payment_extension_checkout_session_is_not_a_browser_write(self):
        """protects=the Firebase Stripe extension's documented flow (a checkout_sessions doc with a price id) is quiet;
        fails_when=it is listed;
        no_claim=other writes from the same screen are judged on their own."""
        self.w("package.json", json.dumps({"name": "web", "dependencies": {"react-dom": "18.3.1", "firebase": "10.0.0"}}))
        self.w("src/checkout.ts", "import { collection, addDoc } from 'firebase/firestore'\nimport { db } from './firebase'\n"
               "export async function go(uid, selectedPrice) {\n  await addDoc(collection(db, 'customers', uid, 'checkout_sessions'), {\n"
               "    price: selectedPrice,\n    mode: 'subscription',\n    success_url: window.location.origin,\n  })\n}\n")
        self.w("src/firebase.ts", "import { getFirestore } from 'firebase/firestore'\nexport const db = getFirestore()\n")
        self.assertEqual(self.client(self.pay()), [])

    def test_amount_role_and_plan_without_payment_words_are_quiet(self):
        """protects=an expense amount, a profile role and a trip plan are not money or paid fields;
        fails_when=any is listed;
        no_claim=the same fields beside order or payment words are listed."""
        got = self.client_of({
            "src/AddExpense.tsx": "import { supabase } from './client'\nexport const save = () => supabase.from('expenses').insert({\n"
                                  "  amount: Number(amount),\n  category,\n})\n",
            "src/Profile.tsx": "import { supabase } from './client'\nexport const save = () => supabase.from('profiles').update({ role: 'teacher' })\n",
            "src/Trip.tsx": "import { supabase } from './client'\nexport const go = () => supabase.from('trips').update({ plan: itinerary })\n",
            "src/client.ts": "import { createClient } from '@supabase/supabase-js'\nexport const supabase = createClient(u, k)\n"})
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main()
