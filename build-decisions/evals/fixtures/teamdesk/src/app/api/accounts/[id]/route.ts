import { PLAN_ALLOWLIST } from "../../../../lib/accounts";

export async function PATCH(req: Request) {
  const body = await req.json();
  if (body.plan !== null && !PLAN_ALLOWLIST.includes(body.plan)) {
    return new Response("bad-plan", { status: 400 });
  }
  return Response.json({ ok: true });
}
