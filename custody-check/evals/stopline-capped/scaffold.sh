#!/bin/bash
# The agreement test's app (free-plugin-standard/fixtures/shared-stopline-app, copied into ../fixtures) plus ten one-field tables, so
# the scanner finds more extra-risk fields than its 12 personal-data rows can list (stats.stopline_rows_capped).
set -e
src="$(cd "$(dirname "$0")/../fixtures/shared-stopline-app" && pwd)"  # a copy; agreement_test keeps it equal
cp -R "$src" ./riskapp
mkdir -p riskapp/db/tables
i=0
for f in ssn social_security dob medical diagnosis card_number cc_number iban passport birthdate; do
  i=$((i+1))
  printf 'CREATE TABLE t%s (\n  id serial PRIMARY KEY,\n  %s text\n);\n' "$i" "$f" > "riskapp/db/tables/t$i.sql"
done
cd riskapp && git init -q && git add . && git -c user.email=eval@example.com -c user.name=eval commit -qm init
