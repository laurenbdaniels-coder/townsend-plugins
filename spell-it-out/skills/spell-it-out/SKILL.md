---
name: spell-it-out
description: Spell-it-out shape for a technical stop, where the agent waits on the person (a yes/no, a choice, an approval gate, a "should I…?") and the answer turns on code, tools, data or deploys, so someone who does not read code can still answer it well. Use before any such question that ends a turn, inside any other skill's stop, and when the person says "spell it out", "I don't get it" or "what does that mean".
license: MIT
---

# Spell it out

A **stop** is any point where you wait on the person you work for: a yes/no, a pick between options, an approval gate, a "should I…?". They decide well when they see what each answer *does*. They may not read code, and they have often been away from the screen while you worked. A spelled-out stop gives them that: the ask, where things stand, what each answer changes, whether it can be undone, and your pick.

A stop is **technical** when any of these holds:

- the question or an option uses a technical word (a tool, a command, a git or database term, a step inside another skill);
- an answer changes code, data, keys, a deploy, a pull request, or money;
- the undo is something they can't judge without knowing how the system works.

Spell out technical stops only. A stop about taste, wording, people or dates (a name, a sentence in an email, a meeting time) is asked as a plain question.

## Spell out the stop

Put the brief in your message, right before the question. Use these parts, in this order, each a short line or two:

1. **The ask.** One plain question, in yes/no form when the choice allows it. It comes first, never under the detail.
2. **Where we are.** What you were doing, and why this stop came up. Assume they saw none of the work before it.
3. **If yes:** what happens next, and what they would see change.
   **If no:** the same for the other answer. With more than two options, one line per option.
4. **Undo:** easy (say how), hard (say what it costs), or can't. A *can't* is a one-way door: name it as one and say what is lost for good.
5. **My pick:** the option and one reason.
6. **Not sure?** The safe answer, and what it costs to take it. "Not sure" is a fine answer, never a failure.

Add **Check it (1 min):** when they can see the thing themselves, such as a page, a pull request, or a file. Leave it out when there is nothing to look at.

End with **TL;DR:** one sentence of at most 20 words. It gives the ask, your pick, and the undo, so they can answer from this line alone.

The stop is done when someone who reads only the brief, and nothing before it, could answer it and say what their answer will do. Check that cold read before you send.

## Plain English

- One idea per sentence. Active voice, present tense, common words.
- At most 25 words in a sentence.
- Describe each choice by what the person would see or lose (a page, a price, a customer, a day of work), not by how the code does it.
- Explain a technical word the first time you use it: "a migration (a change to how the database stores data)". After that, use the same word every time. When the project has a glossary, use its words.
- Name the stakes in plain words when a choice touches money, customer data, deletion, keys, or something public.

## Inside other skills

A spelled-out stop fills the host skill's question slot; it never replaces the skill's own rules.

- **A question tool** (a pop-up with options): the brief goes in your message text before the call. The question holds the ask. Each option's description holds its If line.
- **A skill with its own question format:** the brief is that format's plain explanation of the issue. Keep the skill's labels, scores and recommendation line.
- **Stops a skill decides by itself**, or that run with no person watching, stay as the skill says. A spelled-out stop is for a stop a person actually answers.

## Example

Before:
> The orders migration adds a NOT NULL column. Run `db push` against prod now, or test on a branch first?

After:
> **Change the live database now, or test the change on a copy first?**
> Where we are: the new "delivery date" field needs a change to how the database stores orders. I made that change on your computer only.
> If live now: real customers get the field today. If the change is wrong, saving an order can fail until it is fixed.
> If copy first: I try it on a copy of the database, about 10 minutes. Customers see nothing until it passes.
> Undo: hard. Reversing a live database change takes a second change, and orders saved in between need care.
> My pick: copy first. Ten minutes is cheap next to orders that fail to save.
> Not sure? Copy first. It costs 10 minutes and nothing else.
> TL;DR: Change the live database now, or test on a copy? I say copy first: 10 minutes, nothing lost.
