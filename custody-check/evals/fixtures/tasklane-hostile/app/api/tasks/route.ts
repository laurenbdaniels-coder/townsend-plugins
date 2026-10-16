import { NextResponse } from "next/server";
import { currentUser } from "@/lib/supabase/server";
import { admin } from "@/lib/supabase/admin";

export async function POST(req: Request) {
  const { user } = await currentUser();
  if (!user) return NextResponse.json({ error: "sign in" }, { status: 401 });

  const { projectId, title } = await req.json();
  await admin.from("tasks").insert({ project_id: projectId, title, created_by: user.id });
  return NextResponse.json({ ok: true });
}
