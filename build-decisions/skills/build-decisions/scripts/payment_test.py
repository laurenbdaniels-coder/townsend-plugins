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
            self.assertTrue(s in cs.VOCABULARY or (key == "path" and s in paths), "%s=%r" % (key, s))

    def test_census_and_architecture_lines_unchanged(self):
        """protects=the census and architecture calls print exactly what they printed before the payment section;
        fails_when=adding the payment section changes either line;
        no_claim=the differential test compares both with main on the corpus; this is the local tripwire."""
        self.w("package.json", NEXT_PKG)
        self.w("app/api/stripe/route.ts", UNVERIFIED_HOOK)
        before_c, _, _ = run(self.parent, "app")
        before_a, _, _ = run(self.parent, "app", "--section", "architecture")
        self.pay()
        self.assertNotIn("writers", before_c)
        self.assertNotIn("writers", before_a)
        self.assertEqual(before_a["section"], "architecture")

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

    def test_alias_import_is_unresolved(self):
        """protects=a check that may sit behind a path alias is never called missing;
        fails_when=a handler importing '@/lib/stripe' is listed as not-found;
        no_claim=alias targets are not followed (a known miss, reported as unresolved)."""
        self.w("lib/stripe.ts", "export const verify = (b, s) => stripe.webhooks.constructEvent(b, s, k)\n")
        self.w("app/api/stripe/route.ts", "import { verify } from '@/lib/stripe'\nexport async function POST(req) {\n"
               "  const event = verify(b, s)\n  if (event.type === 'invoice.paid') {}\n}\n")
        self.assertEqual(self.hooks(self.pay()), {"app/api/stripe/route.ts": "unresolved"})

    def test_more_than_five_imports_is_unresolved(self):
        """protects=only the first 5 relative imports are followed, and a check past them is not called missing;
        fails_when=a handler with 6 relative imports and no check in the first 5 is listed as not-found;
        no_claim=import order is source order."""
        for i in range(6):
            self.w("lib/m%d.ts" % i, "export const x%d = 1\n" % i)
        imports = "".join("import { x%d } from '../../../lib/m%d'\n" % (i, i) for i in range(6))
        self.w("app/api/stripe/route.ts", imports + "export async function POST(req) {\n  if (e.type === 'invoice.paid') {}\n}\n")
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

    def test_stopped_walk_with_nothing_is_not_determined(self):
        """protects=a walk that stopped early never reads as 'nothing found';
        fails_when=coverage says complete;
        no_claim=the file limit stands in for every early stop."""
        for i in range(3):
            self.w("lib/f%d.ts" % i, "export const a = 1\n")
        result = self.pay("--max-files", "1")
        self.assertEqual(result["coverage"], "not_determined")
        self.assertTrue(result["partial"])


if __name__ == "__main__":
    unittest.main()
