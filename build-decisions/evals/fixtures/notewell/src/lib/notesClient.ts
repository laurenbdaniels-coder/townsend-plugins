import axios from 'axios'

// Loads the signed-in person's notes from the notes service.
export async function loadNotes() {
  const res = await axios.get('/api/notes')
  return res.data
}
