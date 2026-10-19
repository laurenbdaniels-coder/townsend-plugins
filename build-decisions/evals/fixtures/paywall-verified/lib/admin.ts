import { createClient } from '@supabase/supabase-js'

const supabaseAdmin = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!)

export async function saveSubscription(row: Record<string, unknown>) {
  const { error } = await supabaseAdmin
    .from('subscriptions')
    .upsert([row])
  if (error) throw error
}
