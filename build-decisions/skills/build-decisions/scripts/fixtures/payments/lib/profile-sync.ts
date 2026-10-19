import { supabaseAdmin } from './supabase-admin'
export async function sync(id: string, name: string) {
  const { data } = await supabaseAdmin.from('subscriptions').select('*').eq('user_id', id)
  await supabaseAdmin.from('profiles').update({ full_name: name }).eq('id', id)
  return data
}
