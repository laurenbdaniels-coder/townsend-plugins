#!/bin/bash
set -e
src="$(cd "$(dirname "$0")/../fixtures" && pwd)"
cp -R "$src/bigdesk" ./bigdesk
