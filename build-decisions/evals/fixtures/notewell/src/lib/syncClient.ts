import ky from 'ky'

// Sends edited notes to the sync service.
export async function pushNotes(notes: unknown[]) {
  return ky.post('/api/notes', { json: notes }).json()
}
