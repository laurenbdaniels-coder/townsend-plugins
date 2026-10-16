# spell-it-out

When Claude stops to ask you something technical, it spells it out first.

You built your app by talking to an AI tool. Now and then it stops and asks: "Run the migration against prod?" "Force-push the branch?" "Skip the pre-check?" You have to answer, and the question assumes you know what those words mean and what each answer does.

With spell-it-out, the same stop comes with a short brief:

> **Test the database change on a copy before it goes live?**
> Where we are: the new "delivery date" field needs a change to how the database stores orders. I made that change on your computer only.
> If yes: I try it on a copy of the database, about 10 minutes. Customers see nothing until it passes.
> If no: real customers get the field today. If the change is wrong, saving an order can fail until it is fixed.
> Undo: the copy is easy to throw away. The live change is hard: reversing it takes a second change, and orders saved in between need care.
> My pick: yes. Ten minutes is cheap next to orders that fail to save.
> Not sure? Say yes. It costs 10 minutes, and the live database stays as it is.
> TL;DR: Test on a copy first, since the live change is hard to undo; I say yes, it costs 10 minutes.

## What it does

- **Technical stops only.** A stop is technical when it uses a technical word, when an answer changes code, data, keys, a deploy, a pull request or money, or when you can't judge the undo without knowing how the system works. A question about a name, an email sentence or a meeting time stays a plain question.
- **The same shape every time:** the ask, where we are, what each answer changes, whether you can undo it, Claude's pick, the safe answer if you're not sure, and a one-line TL;DR. When there is something you can look at yourself, it adds a one-minute check.
- **Plain English.** Short sentences. Each technical word is explained the first time it appears.
- **It stays careful.** The safe answer is always one that changes nothing or can be undone. Claude doesn't pick for you when only you know the fact, like what your app stores. "Don't know" is a fine answer there. A reply that doesn't clearly pick an option gets asked again.
- **It fits other skills.** When another skill has its own question format, the brief fills that format's explanation. When a skill gives the exact words of its questions, those words win. It never changes what that skill decides or when.

## Install (Claude Code)

```
/plugin marketplace add laurenbdaniels-coder/townsend-plugins
/plugin install spell-it-out@townsend-plugins
```

Claude reaches for the skill on its own when a stop is technical. You can also type `/spell-it-out:spell-it-out`, or say "spell it out", when a question still doesn't land.

## Make it apply everywhere (optional)

A skill fires when Claude notices it applies. A long task inside another skill can carry Claude past that moment. To make it a standing rule, add these lines to your `CLAUDE.md` (in `~/.claude/` for every project, or in one project's folder):

```
## Stops → spell-it-out
Every technical stop where you wait on me (a yes/no, choice or approval whose answer
turns on code, tools, data or deploys) uses the spell-it-out shape, inside every skill.
It never changes what a skill decides or when, and a skill's exact question wording wins.
Questions about taste, wording, people or dates stay plain questions.
```

## License

MIT. See the repository `LICENSE`.
