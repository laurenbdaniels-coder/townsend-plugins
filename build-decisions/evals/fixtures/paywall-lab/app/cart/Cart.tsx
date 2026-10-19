'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)

export function Cart({ items, userId }: { items: { price: number; qty: number }[]; userId: string }) {
  const placeOrder = async () => {
    const sum = items.reduce((s, i) => s + i.price * i.qty, 0)
    await supabase.from('orders').insert({
      user_id: userId,
      total: sum,
    })
  }
  return <button onClick={placeOrder}>Place order</button>
}
