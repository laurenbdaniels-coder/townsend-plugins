export function Total({ total }: { total: number }) {
  return <strong>Total: ${total.toFixed(2)}</strong>;
}
