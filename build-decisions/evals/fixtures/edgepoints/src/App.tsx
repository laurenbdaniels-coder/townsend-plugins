export default function App() {
  return <button onClick={() => fetch('/functions/v1/award', { method: 'POST', body: JSON.stringify({ playerId: 'me', points: 50 }) })}>Win</button>
}
