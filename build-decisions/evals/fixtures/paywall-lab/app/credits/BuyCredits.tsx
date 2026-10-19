'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)

export function BuyCredits({ profile }: { profile: { id: string; credits: number } }) {
  const buy = async () => {
    await supabase.from('profiles').update({ credits: profile.credits + 10 }).eq('id', profile.id)
  }
  return <button onClick={buy}>Buy 10 credits</button>
}
