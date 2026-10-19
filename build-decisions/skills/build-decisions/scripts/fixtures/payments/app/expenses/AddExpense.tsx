'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!)
export function AddExpense({ amount, category }: { amount: string; category: string }) {
  const save = async () => {
    await supabase.from('expenses').insert({
      amount: Number(amount),
      category,
    })
  }
  return <button onClick={save}>Add</button>
}
