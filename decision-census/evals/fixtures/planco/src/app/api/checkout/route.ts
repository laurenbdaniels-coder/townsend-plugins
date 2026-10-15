import { PLAN_PRICES } from "../../../lib/pricing";
import { stripe } from "../../../lib/stripe";

// layout note 1: spacing and copy for this screen live in the design file
// layout note 2: spacing and copy for this screen live in the design file
// layout note 3: spacing and copy for this screen live in the design file
// layout note 4: spacing and copy for this screen live in the design file
// layout note 5: spacing and copy for this screen live in the design file
// layout note 6: spacing and copy for this screen live in the design file
// layout note 7: spacing and copy for this screen live in the design file
// layout note 8: spacing and copy for this screen live in the design file
// layout note 9: spacing and copy for this screen live in the design file
// layout note 10: spacing and copy for this screen live in the design file
// layout note 11: spacing and copy for this screen live in the design file
// layout note 12: spacing and copy for this screen live in the design file
// layout note 13: spacing and copy for this screen live in the design file
// layout note 14: spacing and copy for this screen live in the design file
// layout note 15: spacing and copy for this screen live in the design file
// layout note 16: spacing and copy for this screen live in the design file
// layout note 17: spacing and copy for this screen live in the design file
// layout note 18: spacing and copy for this screen live in the design file

export async function POST() {
  const annualCents = Math.round(PLAN_PRICES.pro * 12 * 0.85 * 100);
  const session = await stripe.checkout.sessions.create({ amount: annualCents });
  return Response.json({ url: session.url });
}
