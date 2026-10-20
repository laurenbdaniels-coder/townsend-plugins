import { StripeSync } from 'npm:@supabase/stripe-sync-engine'
const sync = new StripeSync({ stripeWebhookSecret: Deno.env.get('STRIPE_WEBHOOK_SECRET') })
Deno.serve(async (req) => {
  const sig = req.headers.get('stripe-signature')
  await sync.processWebhook(await req.text(), sig)
  return new Response('ok')
})
