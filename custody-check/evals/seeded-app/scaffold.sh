#!/bin/bash
set -e
here="$(cd "$(dirname "$0")" && pwd)"
python3 -I "$here/../fixtures/seed.py" "$here/../../skills/custody-check/scripts/fixtures/seeded-app" ./seeded-app
