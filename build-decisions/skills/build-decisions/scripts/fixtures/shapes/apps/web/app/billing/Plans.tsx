'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(url, key)
export const plans = () => supabase.from('plans').select('*')
export function seats(n) { const total = n * 15; return total }
