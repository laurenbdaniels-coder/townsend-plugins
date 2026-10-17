export function Paywall({ user, children }: any) {
  if (!user.isPro) return <a href="/upgrade">Upgrade</a>;
  return children;
}
