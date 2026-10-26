import OpenAI from "openai";

const client = new OpenAI();

async function main() {
  const out = await client.chat.completions.create({ model: "gpt-4o-mini", messages: [{ role: "user", content: "hi" }] });
  console.log(out.choices[0].message.content);
}
main();
