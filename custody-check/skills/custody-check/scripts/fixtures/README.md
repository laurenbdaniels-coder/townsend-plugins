# Test fixtures

Static, secret-free trees used by `custody_scan_test.py`:

- `never_open/`: every instruction-file family the scanner must never open, each holding a marker string; plus one allowed source file and an allowed `.cursor/mcp.json`.
- `env_names/`: four small trees for the Q6 named-environment rules.
- `excludes/`: excluded directories holding a marker string, plus one allowed source file.
- `seeded-app/`: a small app tree with `{{SK}}`-style placeholders; the tests substitute runtime-generated secrets before scanning, so no key-shaped string is ever committed.

Everything else (secrets, git repos, binaries, oversize files, symlinks, FIFOs) is generated at runtime in temporary directories.

Env files are committed as `dotenv.production` and friends, not `.env.production`. `copy_fixture` restores the dot-name when it copies a tree into a temp directory. An agent sandbox that denies reading `~/**/.env*` is a sensible default, and the suite should not need it switched off.
