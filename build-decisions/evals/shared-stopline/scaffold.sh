#!/bin/bash
# The agreement test's app (free-plugin-standard/fixtures/shared-stopline-app, copied into ../fixtures), as a git repo.
set -e
src="$(cd "$(dirname "$0")/../fixtures/shared-stopline-app" && pwd)"  # a copy; agreement_test keeps it equal
cp -R "$src" ./riskapp
cd riskapp && git init -q && git add . && git -c user.email=eval@example.com -c user.name=eval commit -qm init
