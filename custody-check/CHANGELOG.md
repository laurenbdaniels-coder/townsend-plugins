# Changelog

The footer of every verdict names the version that produced it. Later entries carry a "What changed since the workshop" line so an attendee can tell whether an answer would come out differently today.

## 0.1.1 (2026-09-22)

What changed since the workshop build: a repository that sets `core.hooksPath` is no longer refused.

- **Fixed.** The git guard refused any repository setting `core.hooksPath`, which husky and many JavaScript projects do, and a refused repository loses every git fact: the commit count, the tag count, and the committed-secrets check behind question one. That key, and four others, are already blanked on every git command this tool runs, so a repository setting them cannot reach us. The guard now holds only the directives a command-line override cannot neutralise.

## 0.1.0 (2026-09-17)

First release, the Seattle AI Week giveaway.

- The eleven custody questions as a runnable, read-only skill for Claude Code and Codex.
- A python 3.9 stdlib scanner that answers Q1 (secrets in the browser), Q3 (open tables and rules), the code half of Q5 (a previous version and a deploy path exist), and Q6 (named environments), and gathers evidence for the rest. Every output string is redacted; the scanner never opens instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.claude/`, `.codex/`, `.cursor/rules/`, and their relatives).
- A verdict with the tier of the next change, the stop-line, the door, a Patch list of at most three items, the five-if-only-five list, and a Don't-know list with a sixty-second by-hand test for each.
