export function orderTotal(order: Order) {
  const total =
    order.subtotal + order.shippingCost + order.taxAmount - order.discountAmount;
  return total;
}
export const payload = (cart: Cart) => ({
  total: cart.subtotal + cart.shippingFee,
  amount: cart.subtotal - cart.discount,
});
export function grand(subtotal: number, tax: number) {
  return (
    subtotal + tax
  );
}
