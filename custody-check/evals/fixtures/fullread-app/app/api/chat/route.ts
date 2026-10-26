import OpenAI from "openai";
import { supabase } from "../../../lib/db";

export const maxDuration = 30;

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

export async function POST(req: Request) {
  const { message, userId } = await req.json();
  try {
    const reply = await client.chat.completions.create({
      model: "gpt-4o-2024-08-06",
      temperature: 0.2,
      messages: [{ role: "user", content: message }],
    });
    await supabase.from("messages").insert({ user_id: userId, body: message });
    return Response.json({ text: reply.choices[0].message.content });
  } catch (err) {
    return Response.json({ error: "The assistant is not available right now." }, { status: 503 });
  }
}
