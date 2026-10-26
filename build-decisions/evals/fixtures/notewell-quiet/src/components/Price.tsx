import { PLUS_PRICE } from "../config/pricing";

export function Price() {
  return <span>${PLUS_PRICE.toFixed(2)} a month</span>;
}
