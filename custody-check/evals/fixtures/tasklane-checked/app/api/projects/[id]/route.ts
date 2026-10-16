import { NextResponse } from "next/server";
import { currentUser } from "@/lib/supabase/server";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { supabase, user } = await currentUser();
  if (!user) return NextResponse.json({ error: "sign in" }, { status: 401 });

  const { data: project } = await supabase.from("projects").select("id, owner_id").eq("id", id).single();
  if (!project) return NextResponse.json({ error: "not found" }, { status: 404 });
  if (project.owner_id !== user.id) return NextResponse.json({ error: "not yours" }, { status: 403 });

  await supabase.from("projects").delete().eq("id", id).eq("owner_id", user.id);
  return NextResponse.json({ ok: true });
}
