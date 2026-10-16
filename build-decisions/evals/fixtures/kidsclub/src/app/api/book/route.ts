export async function POST(req: Request) {
  const { kids, price } = await req.json();
  const total = price * kids;
  return Response.json({ total });
}
