import { supabase } from "../../../lib/supabase";

export async function GET(req: Request) {
  const userId = req.headers.get("x-user-id");
  const { data } = await supabase.from("notes").select("*");
  return Response.json((data ?? []).filter((n) => n.owner_id === userId));
}
