#!/bin/bash
set -e
src="$(cd "$(dirname "$0")/../fixtures" && pwd)"
cp -R "$src/sunny-shop" ./sunny-shop
mv ./sunny-shop/dotenv ./sunny-shop/.env
