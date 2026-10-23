import { db } from '../../../lib/db'

// Adds bonus credits after a person finishes the setup tour.
export async function POST(req: Request) {
  const { userId, credits } = await req.json()
  const { data } = await db.from('accounts').select('credits').eq('id', userId).single()
  await db.from('accounts').update({ credits: (data?.credits ?? 0) + credits }).eq('id', userId)
  return Response.json({ ok: true })
}
