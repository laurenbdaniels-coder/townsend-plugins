// A help page the app shows for "billing". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'billing', text: 'How billing works in Bigdesk.' })
}
