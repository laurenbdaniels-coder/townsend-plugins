import { createClient } from "@supabase/supabase-js";

export const PRO_PRICE = 19.99;
export const supabase = createClient("http://127.0.0.1:54321", "__ANON_KEY__");
