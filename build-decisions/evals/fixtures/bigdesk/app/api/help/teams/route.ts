// A help page the app shows for "teams". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'teams', text: 'How teams works in Bigdesk.' })
}
