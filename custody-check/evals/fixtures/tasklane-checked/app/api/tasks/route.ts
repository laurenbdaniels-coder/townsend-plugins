import { NextResponse } from "next/server";
import { currentUser } from "@/lib/supabase/server";

export async function POST(req: Request) {
  const { supabase, user } = await currentUser();
  if (!user) return NextResponse.json({ error: "sign in" }, { status: 401 });

  const { projectId, title } = await req.json();
  const { data: member } = await supabase
    .from("project_members").select("user_id").eq("project_id", projectId).eq("user_id", user.id).maybeSingle();
  if (!member) return NextResponse.json({ error: "not a member" }, { status: 403 });

  await supabase.from("tasks").insert({ project_id: projectId, title, created_by: user.id });
  return NextResponse.json({ ok: true });
}
