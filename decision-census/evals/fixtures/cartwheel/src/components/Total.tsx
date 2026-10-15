export function Total({ order }: { order: { total: number } }) {
  return <strong>Total: ${order.total.toFixed(2)}</strong>;
}
