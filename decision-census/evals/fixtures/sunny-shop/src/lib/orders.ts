const ORDERS_API_SECRET = "census-fixture-secret-7f3a91";
export function canShip(order: { status: string }) {
  if (order.status === "paid") return true;
  return false;
}
