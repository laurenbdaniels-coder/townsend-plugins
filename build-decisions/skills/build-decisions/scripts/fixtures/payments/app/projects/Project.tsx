'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
export function Project({ id }: { id: string }) {
  const go = () => supabase.from('projects').update({ status: 'active' }).eq('id', id)
  return <button onClick={go}>Start</button>
}
