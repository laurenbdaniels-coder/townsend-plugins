'use server'
import { db } from '../../lib/db'

// Gives a student points when they finish a study block. The server decides how many.
const POINTS_FOR = { 'finished-block': 10, 'read-chapter': 5 } as const

export async function awardPoints(studentId: string, action: keyof typeof POINTS_FOR) {
  const points = POINTS_FOR[action]
  if (!points) throw new Error('unknown action')
  await db.from('point_events').insert({ student_id: studentId, action, points })
}
