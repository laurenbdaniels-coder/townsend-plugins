// A help page the app shows for "import". Fixed text, nothing saved.
export async function GET() {
  return Response.json({ topic: 'import', text: 'How import works in Bigdesk.' })
}
