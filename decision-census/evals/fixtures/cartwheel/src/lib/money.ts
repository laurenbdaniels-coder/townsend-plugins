// Amount charged to the card.
export function chargeAmount(amount: number): number {
  return Math.round(amount * 100) / 100;
}
