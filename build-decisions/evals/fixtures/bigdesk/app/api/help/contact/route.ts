// A help page the app shows for "contact". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'contact', text: 'How contact works in Bigdesk.' })
}
