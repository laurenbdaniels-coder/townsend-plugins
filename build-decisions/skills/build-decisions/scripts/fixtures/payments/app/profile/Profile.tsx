'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
export function Profile({ id, name }: { id: string; name: string }) {
  const save = () => supabase.from('profiles').update({ role: 'teacher', full_name: name }).eq('id', id)
  return <button onClick={save}>Save</button>
}
