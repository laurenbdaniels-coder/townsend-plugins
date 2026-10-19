import { verifyStripe } from '../../../lib/not-in-this-copy'

export async function POST(req: Request) {
  const event = verifyStripe(await req.text(), req.headers.get('stripe-signature'))
  if (event.type === 'invoice.paid') {
    return new Response('ok')
  }
  return new Response('ignored')
}
