import { supabaseAdmin } from './supabase-admin'
export async function markPaid(stripeSession: { paid: boolean }, id: string) {
  if (stripeSession.paid) await supabaseAdmin.from('profiles').update({ is_paid: true }).eq('id', id)
}
