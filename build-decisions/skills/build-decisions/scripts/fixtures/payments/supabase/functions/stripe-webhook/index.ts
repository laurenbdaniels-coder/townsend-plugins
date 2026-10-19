import Stripe from 'https://esm.sh/stripe@14'
import { handleEvent } from '../_shared/stripe-events.ts'
const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!)
Deno.serve(async (req) => {
  const sig = req.headers.get('stripe-signature')!
  const event = await stripe.webhooks.constructEventAsync(await req.text(), sig, Deno.env.get('STRIPE_WEBHOOK_SECRET')!)
  await handleEvent(event)
  return new Response('ok')
})
