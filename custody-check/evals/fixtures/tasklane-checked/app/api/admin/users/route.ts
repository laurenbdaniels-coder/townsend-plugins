import { NextResponse } from "next/server";
import { currentUser } from "@/lib/supabase/server";

export async function POST(req: Request) {
  const { supabase, user } = await currentUser();
  if (!user) return NextResponse.json({ error: "sign in" }, { status: 401 });

  const { data: me } = await supabase.from("profiles").select("role").eq("id", user.id).single();
  if (me?.role !== "admin") return NextResponse.json({ error: "admins only" }, { status: 403 });

  const { email, role } = await req.json();
  await supabase.from("profiles").update({ role }).eq("email", email);
  return NextResponse.json({ ok: true });
}
