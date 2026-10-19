import { createHmac } from 'crypto'

export async function POST(req: Request) {
  const event = await req.json()
  const logId = createHmac('sha256', 'log').update(event.id).digest('hex')
  if (event.type === 'checkout.session.completed') {
    console.log(logId)
  }
  return new Response('ok')
}
