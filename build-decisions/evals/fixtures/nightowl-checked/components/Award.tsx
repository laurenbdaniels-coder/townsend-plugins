'use client'
import { awardPoints } from '../app/actions/award'

export function AwardButton({ studentId }: { studentId: string }) {
  return <button onClick={() => awardPoints(studentId, 'finished-block')}>I finished a block</button>
}
