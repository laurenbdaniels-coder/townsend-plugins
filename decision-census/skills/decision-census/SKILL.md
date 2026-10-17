---
name: decision-census
description: Decision Census is now Build Decisions. Use when the user says "decision census", "run decision census on", "run decision-census on", or "decision-census". It prints how to install build-decisions and remove this plugin, then stops. It runs nothing and reads nothing.
license: MIT
---

# Decision Census is now Build Decisions

Print exactly this message, word for word, and nothing before or after it:

> Decision Census is now Build Decisions. Run these in your terminal, then start a new session and say 'run build decisions on ./your-app': `claude plugin marketplace update townsend-plugins` · `claude plugin install build-decisions@townsend-plugins` · `claude plugin uninstall decision-census@townsend-plugins`. (Claude Code commands; in Codex or Cowork, reinstall from the townsend-plugins README.)

Then stop. Run no command, open no file and search nothing, whatever the founder asked. Do not run Build Decisions from here, even when it is installed: the founder starts it in a new session.
