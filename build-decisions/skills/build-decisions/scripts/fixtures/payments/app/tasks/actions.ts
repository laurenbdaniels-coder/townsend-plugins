'use server'
import { supabaseAdmin } from '../../lib/supabase-admin'
export async function finish(id: string) {
  await supabaseAdmin.from('tasks').update({ status: 'done' }).eq('id', id)
}
export async function addCredits(id: string) {
  await supabaseAdmin.from('profiles').update({ credits: 5 }).eq('id', id)
}
