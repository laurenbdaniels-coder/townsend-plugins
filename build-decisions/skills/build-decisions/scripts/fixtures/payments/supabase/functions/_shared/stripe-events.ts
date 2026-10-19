import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
const supabase = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
export async function handleEvent(event: any) {
  switch (event.type) {
    case 'checkout.session.completed':
      await supabase.from('profiles').update({ is_paid: true }).eq('id', event.data.object.client_reference_id)
      break
  }
}
