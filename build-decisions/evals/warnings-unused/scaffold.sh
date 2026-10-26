#!/bin/bash
set -e
src="$(cd "$(dirname "$0")/../fixtures" && pwd)"
cp -R "$src/notewell-quiet" ./notewell
# 0.8.0 (S-070): a lockfile covers the app, so unused-parts runs. ky and moment are listed and nothing uses them;
# axios, dayjs and next (its dev script) are used.
cat > ./notewell/package.json <<'JSON'
{
  "name": "notewell",
  "private": true,
  "scripts": {
    "dev": "next dev"
  },
  "dependencies": {
    "axios": "1.7.2",
    "dayjs": "1.11.11",
    "ky": "1.4.0",
    "moment": "2.30.1",
    "next": "15.0.0"
  }
}
JSON
cat > ./notewell/package-lock.json <<'JSON'
{
  "name": "notewell",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": { "name": "notewell" }
  }
}
JSON
