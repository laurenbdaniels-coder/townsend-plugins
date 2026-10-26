export function isPlus(subscription: { status: string }) {
  return subscription.status === "active";
}
