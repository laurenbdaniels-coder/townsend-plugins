// Amount charged to the card for an order.
export function chargeAmount(order: { total: number }): number {
  return Math.round(order.total * 100) / 100;
}
