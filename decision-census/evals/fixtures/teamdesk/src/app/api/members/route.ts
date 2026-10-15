import { ROLE_ALLOWLIST } from "../../../lib/accounts";

export async function POST(req: Request) {
  const { role } = await req.json();
  if (role !== null && !ROLE_ALLOWLIST.includes(role)) return new Response("bad-role", { status: 400 });
  return Response.json({ ok: true });
}
