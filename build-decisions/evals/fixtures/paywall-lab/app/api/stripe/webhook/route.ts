import { supabaseAdmin } from '../../../../lib/supabase-admin'

export async function POST(req: Request) {
  const event = JSON.parse(await req.text())
  if (event.type === 'checkout.session.completed') {
    await supabaseAdmin.from('profiles').update({
      is_paid: true,
    }).eq('id', event.data.object.client_reference_id)
  }
  return new Response('ok')
}
