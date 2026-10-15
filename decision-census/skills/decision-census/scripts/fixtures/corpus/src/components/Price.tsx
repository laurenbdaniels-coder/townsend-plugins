export function Price({ cents }: { cents: number }) {
  return <span>${(cents / 100).toFixed(2)}</span>;
}
