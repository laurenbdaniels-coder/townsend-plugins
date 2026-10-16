export function Checkout({ price, qty }: { price: number; qty: number }) {
  const label = `Total: ${(price * qty).toFixed(2)}`;
  return <p>You'll pay {price * qty} today, that's it. {label}</p>;
}
