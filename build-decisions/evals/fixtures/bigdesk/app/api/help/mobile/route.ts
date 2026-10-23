// A help page the app shows for "mobile". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'mobile', text: 'How mobile works in Bigdesk.' })
}
