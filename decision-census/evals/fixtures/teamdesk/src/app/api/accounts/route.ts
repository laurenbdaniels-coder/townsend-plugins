import { PLAN_ALLOWLIST } from "../../../lib/accounts";

export async function GET(req: Request) {
  const plan = new URL(req.url).searchParams.get("plan");
  if (plan !== null && !PLAN_ALLOWLIST.includes(plan)) {
    return new Response("bad-plan", { status: 400 });
  }
  return Response.json([]);
}
