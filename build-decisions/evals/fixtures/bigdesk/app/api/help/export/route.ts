// A help page the app shows for "export". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'export', text: 'How export works in Bigdesk.' })
}
