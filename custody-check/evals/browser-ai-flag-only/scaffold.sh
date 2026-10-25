#!/bin/bash
# S-064 (custody 0.6.2): see the plan's Step 6 / D4. No key is stored here: any key is built at run time.
set -e
mkdir -p byoapp/src
cat > byoapp/package.json <<'EOF'
{"name": "byoapp", "private": true, "dependencies": {"openai": "4.52.0", "react": "18.3.1"}, "devDependencies": {"vite": "5.3.1"}}
EOF
cat > byoapp/src/ai.ts <<'EOF'
import OpenAI from "openai";

export const openai = new OpenAI({ apiKey: import.meta.env.VITE_MY_AI, dangerouslyAllowBrowser: true });
EOF
cd byoapp && git init -q && git add . && git -c user.email=eval@example.com -c user.name=eval commit -qm init
