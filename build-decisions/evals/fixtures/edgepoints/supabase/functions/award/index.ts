import { createClient } from 'npm:@supabase/supabase-js@2'

// Gives a player points. Runs inside the database service, not in the app's own server code.
Deno.serve(async (req) => {
  const { playerId, points } = await req.json()
  const db = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
  await db.from('players').update({ points }).eq('id', playerId)
  return new Response('ok')
})
