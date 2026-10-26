import axios from 'axios'

export default async function Page() {
  const res = await axios.get('/api/hello')
  return res.data
}
