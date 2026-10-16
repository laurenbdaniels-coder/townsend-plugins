import { supabase } from "../../../lib/db";
import { getUser } from "../../../lib/session";

export async function GET() {
  const user = await getUser();
  const { data } = await supabase.from("projects").select("*").eq("owner_id", user.id);
  return Response.json(data);
}
