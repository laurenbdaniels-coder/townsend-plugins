import { createClient } from '@supabase/supabase-js'

export default async function Dashboard({ userId }: { userId: string }) {
  const supabase = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_ANON_KEY!)
  const { data: profile } = await supabase.from('profiles').select('is_paid, credits').eq('id', userId).single()
  if (!profile?.is_paid) {
    return <a href="/pricing">Upgrade to see your dashboard</a>
  }
  return <p>You have {profile.credits} credits.</p>
}
