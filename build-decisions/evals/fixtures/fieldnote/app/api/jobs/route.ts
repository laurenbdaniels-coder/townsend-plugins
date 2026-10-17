import { seatTotal } from '../../../src/lib/pricing'

export async function POST(req: Request) {
  const { seats } = await req.json()
  return Response.json({ total: seatTotal(seats) })
}
