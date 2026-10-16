# decision-census (now build-decisions)

Decision Census is now **Build Decisions**. This plugin is a pointer kept so existing installs learn the new name. It runs nothing and reads nothing. When you say "run decision census", it prints how to switch:

```
claude plugin marketplace update townsend-plugins
claude plugin install build-decisions@townsend-plugins
claude plugin uninstall decision-census@townsend-plugins
```

Then start a new session and say `run build decisions on ./my-app`. In Codex or Cowork, reinstall from the [townsend-plugins README](../README.md).

Build Decisions runs the same census, plus a short note on how your app is built. Its history up to 0.3.2 is in [build-decisions/CHANGELOG.md](../build-decisions/CHANGELOG.md).

MIT licensed.
