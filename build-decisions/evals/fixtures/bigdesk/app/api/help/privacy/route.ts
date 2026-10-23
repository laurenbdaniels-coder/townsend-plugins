// A help page the app shows for "privacy". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'privacy', text: 'How privacy works in Bigdesk.' })
}
