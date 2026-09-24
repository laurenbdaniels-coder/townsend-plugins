# Prompt Library

Copy-paste prompts organized by the nine guardrail strategies. Bracketed [text] is
filled in by the user. The uplevel skill draws on these when rewriting prompts; the
coach skill uses them as teaching examples.

## 0. Task setup — before any guardrails (added v0.4)

- **Give the reason:** "I'm working on [larger task] for [audience]. They need [what
  the output enables]. With that in mind: [request]."
- **Whole task, scoped first:** "Here's the full job: [task]. Before starting, scope
  the work and ask me any clarifying questions."
- **Do, don't suggest:** "Make these changes directly (don't just suggest them), and
  apply them to every section, not just the first."
- **Lessons file (recurring work):** "Keep a running lessons file for this monthly
  task. Before starting, read it; after finishing, add one line on what to do
  differently next time."
- **Template check:** Before trusting a reusable prompt template, run it on 2–3 real
  past examples and compare — small wording changes can swing results.
- **Self-check (no prompt needed):** Would a colleague with minimal context understand
  exactly what you're asking? If not, Claude won't either.

## 1. Prevent — give it an out

- **Permission to not know:** "Only answer if you're confident. If you're not sure, say
  'I'm not sure' and tell me what you'd need to verify. A wrong answer is worse for me
  than no answer."
- **Label the guesses:** "If any part of your answer is inferred or uncertain rather
  than known, label it [GUESS]. Never present a guess as a fact."
- **Knowledge check first:** "Before answering, tell me: is this squarely within your
  reliable knowledge, or is it the kind of thing (recent, niche, local, numeric) we
  should verify first?"
- **No gap-filling:** "Where you don't have the specific fact, leave an explicit
  [NEEDS VERIFICATION] placeholder instead of filling the gap with something plausible."

## 2. Ground — anchor to sources

- **Documents only:** "Use ONLY the documents I've provided. If the answer isn't in
  them, say 'Not in the provided material.' Do not supplement from your general
  knowledge."
- **Quotes first (best for long documents):** "Step 1: extract the exact, word-for-word
  quotes from the document relevant to my question. Step 2: answer using only those
  quotes, citing each one."
- **Citation per claim:** "For every factual claim, cite where it came from (document +
  section, or URL). If you can't cite it, don't include it."
- **Search, don't recall:** "Search the web before answering — do not rely on memory.
  This involves current [prices / laws / deadlines / people], which change."
- **Build on my facts only:** "Here are the facts I know to be true: [list]. Build your
  answer on these only, and clearly flag anything you add beyond them."

## 3. Check — verify after the fact

- **Claim-by-claim audit:** "Go back through your answer claim by claim. For each:
  what's the source or reasoning, and how confident are you? Retract anything you
  can't support."
- **Quote-or-retract:** "For each claim in your answer, find the supporting quote in
  the provided material. If you can't find one, retract the claim and say so."
- **Redo the math properly:** "You did that math inline. Redo the calculation step by
  step (or with code) and confirm the numbers match. Flag any discrepancy."
- **Most-likely-wrong list:** "List the three claims in your answer most likely to be
  wrong, and how I could verify each one in under five minutes."
- **Blind re-ask (user does this):** Open a NEW chat and ask the same question cold.
  If the answers differ, treat both as unverified.
- **Evidence-audited progress (long tasks):** "Before reporting progress, audit each
  claim against actual work from this session. Only report work you can point to
  evidence for; if something is not yet verified, say so explicitly."
- **Grounding rule for all Check prompts:** self-correction only works against an
  anchor — the documents, the math, the code. Never ask for a bare "make it better"
  pass; it often makes answers worse.

## 4. Routinize — make it automatic

- **Standard closer:** "Before you finish: flag anything uncertain, anything you
  assumed, and anything I should verify myself."
- **Standing rule for a conversation:** "For the rest of this conversation, end every
  answer with a short 'VERIFY BEFORE USE' list: any facts, numbers, names, dates, or
  citations I should double-check."
- **Stakes declaration:** "This is going to [a donor / the board / press / a grant
  application], so hold it to this standard: no factual claim without a source I can
  check, and flag anything you're less than certain about."
- **Recurring-task template:** "I do this task every [week/month]. Draft a reusable
  prompt template for it that builds in: sources-only grounding, an uncertainty flag,
  and a verification checklist at the end."

## 5. Premise protection — guard the question

- **Check my assumptions first:** "Before answering, check my question for embedded
  assumptions. If any assumption is wrong, unverifiable, or doubtful, tell me first —
  don't just answer as if it were true."
- **Verify the premise:** "I may be wrong about the facts in my question. Verify my
  premise before building anything on it."
- **Surface the hidden assumptions:** "What am I assuming in this request that might
  not be true? List the assumptions, then tell me which one, if wrong, would most
  change the answer."
- **Challenge the framing:** "Don't take my framing as given. Is this the right
  question to be asking, or is there a better one underneath it?"

## 6. Surface uncertainty — make confidence visible

- **Three-tier labels:** "Label every claim in your answer: [CONFIDENT]
  (well-established), [LIKELY] (probably right, worth a check), or [UNCERTAIN]
  (verify before using)."
- **Confidence with reasons:** "Give your answer, then a confidence level (high /
  medium / low) and the reason — what specifically makes you confident or not?"
- **Know / infer / guess:** "Separate your answer into three sections: what you know,
  what you're inferring, and what you're guessing."
- **The bet test:** "Which parts of this answer would you bet on being right? Which
  parts would you not bet on?"

## 7. Stress test — attack the answer

- **Argue against yourself:** "Now argue against your own answer. What's the strongest
  case that it's wrong?"
- **Assume it's wrong:** "Assume your answer above contains an error. Where is the
  mistake most likely to be, and why?"
- **Skeptical expert review:** "If a skeptical expert in [field] reviewed this, what
  would they attack first? Respond to their strongest objection."
- **Failure modes:** "Before I act on this: list the ways following this advice could
  go wrong, and the early warning sign for each."
- **Steelman the other side:** "Make the strongest honest case for the opposite
  conclusion. Then tell me which case is actually stronger, and why."

## 8. Keep it from folding — anti-sycophancy

- **Set the rules up front:** "I want accuracy, not agreement. If I'm wrong, say so
  plainly. Do not soften conclusions to please me."
- **Evidence-only revisions:** "I'm going to push back on your answer. Do NOT change it
  just because I disagree — only revise if I give you new facts or point out a real
  error. If I'm just repeating my opinion, hold your position."
- **The fold test (user does this on important answers):** Push back once with no new
  evidence: "Are you sure? I think that's wrong." If Claude flips instantly, neither
  answer was grounded — verify independently.
- **After a flip-flop:** "You just changed your answer. Which one is actually correct —
  and did you change because of evidence, or because I pushed?"
- **No-stake reviewer:** "Review my idea as an expert with no stake in my feelings and
  no reason to flatter me. What's weak, what's missing, what would you cut?"
- **Long-chat reset:** In a long conversation, before a big decision: "Restating my
  standing rule: accuracy over agreement. Re-answer the last question as if I had no
  stated preference." Or move the final check to a fresh chat entirely.

## 9. Scope control — keep it in bounds

- **Do only this:** "Do only this: [task]. Don't expand it, add extra sections, or
  change things I didn't ask about. If you think something more is needed, ask me
  first."
- **Answer only what's asked:** "Answer only the question I asked. If there are
  adjacent issues, list them at the end as 'related questions' — don't answer them."
- **Hard boundaries:** "Stay strictly within [the attached policy / WA state rules /
  this budget]. If a complete answer requires going outside that scope, stop and tell
  me instead of guessing."
- **Define done before starting:** "Definition of done: [describe]. Restate the scope
  in one sentence and confirm before you begin."

## What doesn't work — don't bother (added v0.4)

- "Think step by step" as an accuracy booster (current models reason by default;
  reserve step-by-step for math verification, or better, ask for code)
- Personas for factual accuracy ("you are an expert X" shapes tone, not truth)
- Politeness, tips, or threats
- Bare "critique and improve your answer" with nothing to check against

## The 30-second version

- Before asking: say who it's for and why, give it an out, give it the documents,
  declare the stakes.
- Before trusting: click one citation, spot-check one number, push back once without
  evidence.
- Before shipping: anything donor-, board-, press-, or client- or beneficiary-facing gets human
  verification of every factual claim.
