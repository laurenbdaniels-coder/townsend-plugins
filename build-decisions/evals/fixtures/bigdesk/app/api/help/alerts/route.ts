// A help page the app shows for "alerts". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'alerts', text: 'How alerts works in Bigdesk.' })
}
