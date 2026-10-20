import { db } from '@/lib/db'

export async function POST(req: Request) {
  const event = await req.json()
  if (event.type === 'invoice.paid') {
    return new Response('ok')
  }
  return new Response('ignored')
}
