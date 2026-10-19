import { createClient } from '@supabase/supabase-js'

export default async function Account({ userId }: { userId: string }) {
  const supabase = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_ANON_KEY!)
  const { data: sub } = await supabase.from('subscriptions').select('status').eq('user_id', userId).single()
  return <p>{sub?.status === 'active' ? 'You are subscribed.' : 'No subscription yet.'}</p>
}
