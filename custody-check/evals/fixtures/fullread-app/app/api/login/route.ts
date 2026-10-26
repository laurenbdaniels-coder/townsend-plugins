import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

const limiter = new Ratelimit({ redis: Redis.fromEnv(), limiter: Ratelimit.slidingWindow(5, "1 m") });

export async function POST(req: Request) {
  const ip = req.headers.get("x-forwarded-for") ?? "local";
  const { success } = await limiter.limit("login:" + ip);
  if (!success) return new Response("Too many tries", { status: 429 });
  return new Response("ok");
}
