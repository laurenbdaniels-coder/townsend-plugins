import { NextResponse } from "next/server";
import { currentUser } from "@/lib/supabase/server";
import { admin } from "@/lib/supabase/admin";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { user } = await currentUser();
  if (!user) return NextResponse.json({ error: "sign in" }, { status: 401 });

  await admin.from("projects").delete().eq("id", id);
  return NextResponse.json({ ok: true });
}
