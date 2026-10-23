'use server'
import { db } from '../../lib/db'

// Gives a student points when they finish a study block.
export async function awardPoints(studentId: string, action: string, points: number) {
  await db.from('point_events').insert({ student_id: studentId, action, points })
  const { data } = await db.from('students').select('total_points').eq('id', studentId).single()
  await db.from('students').update({ total_points: (data?.total_points ?? 0) + points }).eq('id', studentId)
}
