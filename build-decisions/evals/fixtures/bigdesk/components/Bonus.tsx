'use client'

export function TourDone({ userId }: { userId: string }) {
  async function finish() {
    await fetch('/api/bonus', { method: 'POST', body: JSON.stringify({ userId, credits: 50 }) })
  }
  return <button onClick={finish}>Finish the tour</button>
}
