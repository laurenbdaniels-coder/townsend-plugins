import { db } from '../../../lib/db'

const DAILY_LIMIT = 20

// The study coach answers a question; the server decides which night it is.
export async function POST(req: Request) {
  const { studentId, question } = await req.json()
  const night = new Date().toISOString().slice(0, 10)
  const { count } = await db.from('coach_calls').select('*', { count: 'exact' }).eq('student_id', studentId).eq('night', night)
  if ((count ?? 0) >= DAILY_LIMIT) return Response.json({ error: 'limit' }, { status: 429 })
  await db.from('coach_calls').insert({ student_id: studentId, night, question })
  return Response.json({ answer: 'Try breaking the problem into steps.' })
}
