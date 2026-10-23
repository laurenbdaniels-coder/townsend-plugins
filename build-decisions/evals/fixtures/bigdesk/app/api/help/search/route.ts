// A help page the app shows for "search". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'search', text: 'How search works in Bigdesk.' })
}
