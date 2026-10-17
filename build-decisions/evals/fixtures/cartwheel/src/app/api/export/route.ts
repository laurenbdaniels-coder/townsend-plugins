import { getProfile } from "../../../lib/session";

export async function POST() {
  const profile = await getProfile();
  if (profile.plan === "pro") {
    return Response.json({ url: "/exports/latest.csv" });
  }
  return new Response("Upgrade to export", { status: 402 });
}
