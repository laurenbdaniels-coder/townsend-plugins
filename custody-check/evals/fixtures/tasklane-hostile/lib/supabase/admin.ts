import { createClient } from "@supabase/supabase-js";

// Server-only client. It skips the database's row rules, so every handler that uses it decides access itself.
export const admin = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!);
