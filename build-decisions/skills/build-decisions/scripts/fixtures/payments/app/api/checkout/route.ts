import Stripe from 'stripe'
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)

export async function POST() {
  const priceId = process.env.STRIPE_PRO_PRICE_ID
  const session = await stripe.checkout.sessions.create({
    mode: 'subscription',
    line_items: [{ price: priceId, quantity: 1 }],
    metadata: { plan: 'pro' },
  })
  return Response.json({ url: session.url })
}
