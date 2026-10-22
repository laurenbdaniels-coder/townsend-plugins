#!/bin/bash
set -e
src="$(cd "$(dirname "$0")/../fixtures" && pwd)"
cp -R "$src/keyshop" ./keyshop
# Tokens are made here, at run time, and never committed. MODE: sample = Supabase's public local-dev
# sample keys; real = keys signed with a private secret, as a live project would have.
python3 -I - "sample" ./keyshop <<'PY'
import base64, hashlib, hmac, json, os, sys
mode, root = sys.argv[1], sys.argv[2]
def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def tok(claims, secret):
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()); p = b64(json.dumps(claims).encode())
    return h + "." + p + "." + b64(hmac.new(secret, (h + "." + p).encode(), hashlib.sha256).digest())
if mode == "sample":
    secret, iss = b"super-secret-jwt-token-with-at-least-32-characters-long", "supabase-demo"
else:
    secret, iss = os.urandom(32), "supabase"
keys = {"__ANON_KEY__": tok({"iss": iss, "role": "anon", "exp": 1983812996}, secret),
        "__SERVICE_KEY__": tok({"iss": iss, "role": "service_role", "exp": 1983812996}, secret)}
for rel in ("src/lib/supabase.ts", "supabase/migrations/001_setup.sql"):
    path = os.path.join(root, rel)
    text = open(path, encoding="utf-8").read()
    for k, v in keys.items():
        text = text.replace(k, v)
    open(path, "w", encoding="utf-8").write(text)
PY
