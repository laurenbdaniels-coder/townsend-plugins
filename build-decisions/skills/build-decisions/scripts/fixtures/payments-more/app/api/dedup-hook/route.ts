import { createHmac } from 'crypto'

export async function POST(req: Request) {
  const event = await req.json()
  const key = createHmac('sha256', process.env.DEDUP_KEY!).update(event.id).digest('hex')
  if (key === (await kv.get('last-event'))) return new Response('duplicate')
  if (event.type === 'checkout.session.completed') {
    return new Response('ok')
  }
  return new Response('ignored')
}
