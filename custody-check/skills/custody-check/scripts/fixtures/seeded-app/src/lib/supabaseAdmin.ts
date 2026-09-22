import { createClient } from "@supabase/supabase-js";
export const admin = createClient(process.env.SUPABASE_URL as string, "{{SERVICE_JWT}}");
