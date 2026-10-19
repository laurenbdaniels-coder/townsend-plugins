'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)

export default function Success({ userId }: { userId: string }) {
  supabase.from('profiles').update({ is_paid: true }).eq('id', userId)
  return <p>Thanks for upgrading!</p>
}
