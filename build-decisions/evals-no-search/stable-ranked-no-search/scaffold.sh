#!/bin/bash
set -e
src="$(cd "$(dirname "$0")/../../evals/fixtures" && pwd)"
cp -R "$src/rankly" ./rankly
