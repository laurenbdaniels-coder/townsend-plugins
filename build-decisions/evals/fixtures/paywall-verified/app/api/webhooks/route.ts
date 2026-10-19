import { readEvent } from '../../../lib/stripe'
import { saveSubscription } from '../../../lib/admin'

export async function POST(req: Request) {
  const event = readEvent(await req.text(), req.headers.get('stripe-signature'))
  if (event.type === 'customer.subscription.updated' || event.type === 'customer.subscription.deleted') {
    const sub = event.data.object as { id: string; status: string; customer: string }
    await saveSubscription({ id: sub.id, status: sub.status, customer: sub.customer })
  }
  return new Response(JSON.stringify({ received: true }))
}
