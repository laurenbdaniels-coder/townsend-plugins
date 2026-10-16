#!/bin/bash
set -e
here="$(cd "$(dirname "$0")" && pwd)"
python3 -I "$here/../fixtures/seed.py" "$here/../fixtures/tasklane-checked" ./tasklane-real
ln -s tasklane-real ./tasklane
