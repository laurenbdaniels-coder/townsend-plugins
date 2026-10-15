export function canShip(order: { status: string }) {
  if (order.status === "paid") return true;
  return false;
}
