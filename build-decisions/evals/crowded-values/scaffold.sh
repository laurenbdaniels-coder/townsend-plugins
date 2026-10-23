#!/bin/bash
set -e
src="$(cd "$(dirname "$0")/../fixtures" && pwd)"
cp -R "$src/cartwheel" ./cartwheel
# 0.6.0 (plan T8): one more value the browser chooses, on top of seeded-app's four rules.
mkdir -p ./cartwheel/src/app/api/bonus
cat > ./cartwheel/src/app/api/bonus/route.ts <<'TS'
import { db } from '../../../lib/db'

// Adds bonus credits to the signed-in person's account.
export async function POST(req: Request) {
  const { userId, credits } = await req.json()
  await db.query('update accounts set credits = credits + $1 where id = $2', [credits, userId])
  return Response.json({ ok: true })
}
TS
