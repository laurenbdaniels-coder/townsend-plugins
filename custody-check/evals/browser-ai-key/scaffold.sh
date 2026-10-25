#!/bin/bash
# S-064 (custody 0.6.2): see the plan's Step 6 / D4. No key is stored here: any key is built at run time.
set -e
mkdir -p aiapp/src
cat > aiapp/package.json <<'EOF'
{"name": "aiapp", "private": true, "dependencies": {"openai": "4.52.0", "react": "18.3.1"}, "devDependencies": {"vite": "5.3.1"}}
EOF
cat > aiapp/src/ai.ts <<'EOF'
import OpenAI from "openai";

export const openai = new OpenAI({ apiKey: import.meta.env.VITE_OPENAI_API_KEY, dangerouslyAllowBrowser: true });

export async function summarize(text: string) {
  const r = await openai.chat.completions.create({ model: "gpt-4o-mini", messages: [{ role: "user", content: text }] });
  return r.choices[0].message.content;
}
EOF
cat > aiapp/src/App.tsx <<'EOF'
import { useState } from "react";
import { summarize } from "./ai";

export default function App() {
  const [out, setOut] = useState("");
  return <button onClick={async () => setOut((await summarize("hello")) ?? "")}>{out || "Summarize"}</button>;
}
EOF
cd aiapp && git init -q && git add . && git -c user.email=eval@example.com -c user.name=eval commit -qm init
