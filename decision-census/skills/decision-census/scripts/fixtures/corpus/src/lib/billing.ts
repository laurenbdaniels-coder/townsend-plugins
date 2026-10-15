export function hasAccess(subscription: { status: string }) {
  if (subscription.status === "active") {
    return true;
  }
  return false;
}
