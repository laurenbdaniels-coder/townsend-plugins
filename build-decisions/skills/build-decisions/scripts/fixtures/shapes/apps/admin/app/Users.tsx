'use client'
import { createClient } from '@supabase/supabase-js'
const supabase = createClient(url, key)
export const fee = (amount) => amount * 0.03
export const users = () => supabase.from('users').select('*')
