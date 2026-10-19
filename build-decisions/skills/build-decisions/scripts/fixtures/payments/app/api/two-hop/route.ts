import { verifyEvent } from '../../../lib/hook-relay'

export async function POST(req: Request) {
  const event = verifyEvent(await req.text(), req.headers.get('stripe-signature'))
  if (event.type === 'invoice.paid') {
    return new Response('ok')
  }
  return new Response('ignored')
}
