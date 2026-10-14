export function shippingCost(weight: number) {
  const shipping = weight * 0.5;
  const handlingFee = weight * 0.1 + 2;
  return shipping + handlingFee;
}
