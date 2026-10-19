export async function POST(req: Request) {
  // const event = stripe.webhooks.constructEvent(body, sig, secret)
  const event = await req.json()
  if (event.type === 'invoice.paid') {
    return new Response('ok')
  }
  return new Response('ignored')
}
