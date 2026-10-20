export async function POST(req: Request) {
  const { verifyStripe } = await import(`../../../lib/stripe-verify`)

  const event = verifyStripe(await req.text(), req.headers.get('stripe-signature'))
  if (event.type === 'customer.subscription.updated') {
    return new Response('ok')
  }
  return new Response('ignored')
}
