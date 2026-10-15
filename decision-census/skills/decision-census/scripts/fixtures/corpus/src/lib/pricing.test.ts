import { lineTotal } from "./pricing";
it("multiplies price by quantity", () => {
  expect(lineTotal(2, 3)).toBe(2 * 3);
  const total = 2 * 3;
});
