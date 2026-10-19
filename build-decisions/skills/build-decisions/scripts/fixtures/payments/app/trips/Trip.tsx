'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
export function Trip({ id, itinerary }: { id: string; itinerary: string }) {
  const go = () => supabase.from('trips').update({ plan: itinerary }).eq('id', id)
  return <button onClick={go}>Save</button>
}
