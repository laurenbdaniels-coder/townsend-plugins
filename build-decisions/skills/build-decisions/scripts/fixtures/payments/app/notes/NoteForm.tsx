'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
export function NoteForm({ id }: { id: string }) {
  // supabase.from('profiles').update({ is_paid: true })
  const save = (title: string) => supabase.from('notes').update({ title }).eq('id', id)
  return <form onSubmit={() => save('x')} />
}
