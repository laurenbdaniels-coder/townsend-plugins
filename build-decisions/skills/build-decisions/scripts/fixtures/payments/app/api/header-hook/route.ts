import Stripe from 'stripe'
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)

export async function POST(req: Request) {
  const body = await req.text()
  stripe.webhooks.signature.verifyHeader(body, req.headers.get('stripe-signature')!, process.env.STRIPE_WEBHOOK_SECRET!)
  const event = JSON.parse(body)
  if (event.type === 'invoice.paid') {
    return new Response('ok')
  }
  return new Response('ignored')
}
