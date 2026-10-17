import { supabase } from "../../../lib/db";

export async function GET(req: Request, session: any) {
  const { data } = await supabase.from("notes").select("*").eq("user_id", session.user.id);
  return Response.json(data);
}
