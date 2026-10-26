import axios from 'axios'

// Sends edited notes to the sync service.
export async function pushNotes(notes: unknown[]) {
  return (await axios.post('/api/notes', notes)).data
}
