import { lineTotal } from "../../lib/pricing";

export async function POST(req: Request) {
  const { items } = await req.json();
  const subtotal = items.reduce((s: number, i: any) => s + lineTotal(i.price, i.qty), 0);
  const tax = 0.08;
  const total = subtotal + subtotal * tax;
  return Response.json({ total });
}
