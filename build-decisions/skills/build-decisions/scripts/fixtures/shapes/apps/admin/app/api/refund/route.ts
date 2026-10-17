export async function POST() {
  const total = seats * 15
  return Response.json({ total })
}
