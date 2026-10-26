import { sortBy } from 'lodash'
import { z } from 'zod'

const Name = z.string()

export function App() {
  return <ul>{sortBy([Name.parse('b'), 'a']).map((n) => <li key={n}>{n}</li>)}</ul>
}
