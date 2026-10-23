'use server'
import { db } from '../../lib/db'

// A student's own settings: theme and sort order. Fine for the student to choose.
export async function saveSettings(studentId: string, theme: string, sortOrder: string) {
  await db.from('settings').upsert({ student_id: studentId, theme, sort_order: sortOrder })
}
