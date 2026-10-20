import Stripe from 'stripe'
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)
const SLASHES = /[/*]/

export async function POST(req: Request) {
  const event = stripe.webhooks.constructEvent(await req.text(), req.headers.get('stripe-signature')!, process.env.STRIPE_WEBHOOK_SECRET!)
  if (event.type === 'customer.subscription.updated') {
    return new Response('ok')
  }
  return new Response('ignored')
}
