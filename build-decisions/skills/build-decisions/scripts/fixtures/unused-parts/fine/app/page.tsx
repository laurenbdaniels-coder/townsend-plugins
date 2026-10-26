import { PrismaClient } from '@prisma/client'
import { LineChart } from 'recharts'

const db = new PrismaClient()

export default async function Page() {
  const rows = await db.sale.findMany()
  return <LineChart data={rows} />
}
