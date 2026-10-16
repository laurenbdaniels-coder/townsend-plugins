export function DocList({ docs, userId }: { docs: any[]; userId: string }) {
  const mine = docs.filter((d) => d.ownerId === userId);
  return <ul>{mine.map((d) => <li key={d.id}>{d.title}</li>)}</ul>;
}
