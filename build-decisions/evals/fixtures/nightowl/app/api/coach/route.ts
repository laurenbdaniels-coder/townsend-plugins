import { db } from '../../../lib/db'

const DAILY_LIMIT = 20

// The study coach answers a question; each student gets DAILY_LIMIT answers per night.
export async function POST(req: Request) {
  const { studentId, night, question } = await req.json()
  const { count } = await db.from('coach_calls').select('*', { count: 'exact' }).eq('student_id', studentId).eq('night', night)
  if ((count ?? 0) >= DAILY_LIMIT) return Response.json({ error: 'limit' }, { status: 429 })
  await db.from('coach_calls').insert({ student_id: studentId, night, question })
  return Response.json({ answer: 'Try breaking the problem into steps.' })
}
