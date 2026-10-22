import { stripe } from "../../../lib/stripe";

const PRO_PRICE = 19.99;

export async function POST() {
  const session = await stripe.checkout.sessions.create({ amount: Math.round(PRO_PRICE * 100) });
  return Response.json({ url: session.url });
}
