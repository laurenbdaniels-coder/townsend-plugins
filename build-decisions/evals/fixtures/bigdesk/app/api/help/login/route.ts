// A help page the app shows for "login". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'login', text: 'How login works in Bigdesk.' })
}
