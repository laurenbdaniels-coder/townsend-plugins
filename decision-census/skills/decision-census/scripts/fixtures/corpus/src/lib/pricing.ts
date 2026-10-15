// Line items for the cart.
export function lineTotal(unitPrice: number, quantity: number): number {
  return unitPrice * quantity;
}
