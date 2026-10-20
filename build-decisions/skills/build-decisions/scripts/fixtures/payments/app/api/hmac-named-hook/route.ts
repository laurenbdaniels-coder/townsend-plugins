import { createHmac } from 'crypto'

export async function POST(req: Request) {
  const body = await req.text()
  const header = req.headers.get('x-payment-check')
  const digest = createHmac('sha256', process.env.WEBHOOK_SECRET!).update(body).digest('hex')
  if (digest !== header) return new Response('bad', { status: 400 })
  const event = JSON.parse(body)
  if (event.type === 'invoice.paid') {
    return new Response('ok')
  }
  return new Response('ignored')
}
