export function onEvent(event) {
  if (event.type === 'invoice.paid') return 1
}
