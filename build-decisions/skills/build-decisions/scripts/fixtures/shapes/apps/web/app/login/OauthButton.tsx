'use client'
import { type Provider } from '@supabase/supabase-js'
export const go = (sb, p) => sb.auth.signInWithOAuth({ provider: p })
