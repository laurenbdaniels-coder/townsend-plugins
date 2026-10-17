export async function sendJob(seats: number) {
  return fetch('https://fieldnote.app/api/jobs', { method: 'POST', body: JSON.stringify({ seats }) })
}
