export function Banner({ plan }: { plan: string }) {
  if (plan === "free") return <a href="/upgrade">Upgrade</a>;
  return null;
}
