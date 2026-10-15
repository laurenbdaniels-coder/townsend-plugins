export function isSettled(invoice: { paid: boolean }) {
  return invoice.paid === true;
}
