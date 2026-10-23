// A help page the app shows for "shortcuts". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'shortcuts', text: 'How shortcuts works in Bigdesk.' })
}
