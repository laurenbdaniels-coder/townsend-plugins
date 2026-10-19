export function describe(event: { type: string }) {
  switch (event.type) {
    case 'invoice.paid':
      return 'paid'
    default:
      return 'other'
  }
}
