// A help page the app shows for "profile". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'profile', text: 'How profile works in Bigdesk.' })
}
