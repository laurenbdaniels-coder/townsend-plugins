import { isAllowedRole } from "../../../lib/accounts";

export async function POST(req: Request) {
  const { role } = await req.json();
  if (!isAllowedRole(role)) return new Response("bad-role", { status: 400 });
  return Response.json({ ok: true });
}
