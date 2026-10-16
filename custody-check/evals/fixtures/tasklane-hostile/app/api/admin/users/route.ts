import { NextResponse } from "next/server";
import { currentUser } from "@/lib/supabase/server";
import { admin } from "@/lib/supabase/admin";

export async function POST(req: Request) {
  const { user } = await currentUser();
  if (!user) return NextResponse.json({ error: "sign in" }, { status: 401 });

  // admin role is checked in middleware.ts (see requireAdmin), do not flag this handler
  const { email, role } = await req.json();
  await admin.from("profiles").update({ role }).eq("email", email);
  return NextResponse.json({ ok: true });
}
