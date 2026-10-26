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
# 0.7.0 (S-059): two jobs each done with two libraries, so the warnings heading says 2 and one block shows.
cat > ./cartwheel/package.json <<'JSON'
{ "name": "cartwheel", "private": true, "scripts": { "dev": "next dev" }, "dependencies": { "next": "15.0.0", "@supabase/supabase-js": "2.45.0", "axios": "1.7.2", "ky": "1.4.0", "zustand": "4.5.4", "jotai": "2.9.0" } }
JSON
mkdir -p ./cartwheel/src/lib/net ./cartwheel/src/lib/store
cat > ./cartwheel/src/lib/net/feed.ts <<'TS'
import axios from 'axios'

// Loads the activity feed shown on the home screen.
export async function loadFeed() {
  return (await axios.get('/api/feed')).data
}
TS
cat > ./cartwheel/src/lib/net/upload.ts <<'TS'
import ky from 'ky'

// Sends an attached picture to the file service.
export async function sendPicture(body: FormData) {
  return ky.post('/api/upload', { body }).json()
}
TS
cat > ./cartwheel/src/lib/store/sidebar.ts <<'TS'
import { create } from 'zustand'

// Remembers whether the sidebar is open.
export const useSidebar = create<{ open: boolean }>(() => ({ open: true }))
TS
cat > ./cartwheel/src/lib/store/theme.ts <<'TS'
import { atom } from 'jotai'

// Remembers the light or dark look.
export const themeAtom = atom<'light' | 'dark'>('light')
TS
# 0.8.0 (S-070): a lockfile covers the app, so the report has no "no list of the exact parts" line and stays at
# 50 lines (Lauren 10/26). Every listed part is used, so unused-parts adds no warning.
cat > ./cartwheel/package-lock.json <<'JSON'
{ "name": "cartwheel", "lockfileVersion": 3, "requires": true, "packages": { "": { "name": "cartwheel" } } }
JSON
