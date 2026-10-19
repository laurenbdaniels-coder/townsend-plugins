import { PRO_PRICE } from '../../lib/plans'

export default function Pricing() {
  return (
    <main>
      <h1>Go Pro</h1>
      <p>${PRO_PRICE} a month</p>
      <form action="/api/checkout" method="POST"><button>Upgrade</button></form>
    </main>
  )
}
