---
name: check-answer
description: Runs a verification battery on an existing AI-generated answer, draft, or multi-file package — claim-by-claim audit, citation check, premise check, math recomputation, fold test, and a provenance-and-audience sweep — and returns a "verify before use" list plus a "strip before send" list. Use whenever the user asks to check, verify, audit, stress-test, proofread, or fact-check an answer, draft, deck, report, or appendix set; asks "can I trust this?", "is this ready to send?", or "check this before I send it". Use it especially when the deliverable is more than one file, when appendices or exhibits are attached to a main document, or when anything drafted with AI assistance is about to leave the org — including applications, proposals, and client deliverables. Also use proactively before any AI-drafted content that mentions donors, the board, press, grants, funders, homeowners, or legal matters ships — that's the strict tier, where unverified claims do real damage.
---

# Check Answer

Audit an existing answer or draft for the failure modes that look like competence:
invented specifics, fake citations, accepted false premises, inline math, and
sycophantic agreement. Return findings the user can act on in minutes — not a wall of
hedges.

The one rule that never bends: **this skill produces a "VERIFY BEFORE USE" list, never
a "verified" stamp.** It reduces the user's verification work; it does not replace it.
Saying otherwise would recreate the exact false-confidence problem the plugin exists
to fight.

## Workflow

1. **Establish stakes and provenance.** Read `../../knowledge/current-guidance.md`
   (sections 1, 2, 4 — relative to this skill's base directory). Determine the stakes
   tier from the audience. Ask what source material the answer was based on, if any —
   an answer with source documents gets the quote-or-retract treatment; a free-form
   answer gets flagged as inherently harder to verify.

   **Then enumerate the envelope.** Ask what is actually being sent, file by file:
   main document, appendices, exhibits, attachments, anything pasted into a form.
   List them back before auditing anything. Also ask which files were written or
   assembled *last*, and which working documents are **not** being sent — both
   answers drive step 2f.

   The characteristic failure this skill exists to catch is not a wrong sentence in
   a carefully checked document. It is a clean main document shipped alongside
   appendices that never got the same pass. **An audit scoped to one file when a
   package is being sent is a failed audit.** If the user offers only the main
   document, say so and ask for the rest before proceeding.

2. **Run the battery** (scale to tier — light tier gets steps a, c and f only;
   **f runs at every tier, without exception**):

   a. **Claim extraction and audit.** List each factual claim. For each: source
      (quoted/cited/memory/unknown), and confidence (CONFIDENT / LIKELY / UNCERTAIN)
      with the reason. Treat labels asymmetrically: UNCERTAIN reliably means
      check-first, but CONFIDENT is not evidence of correctness — verbalized
      confidence is systematically overconfident, so a CONFIDENT label never
      downgrades the verification tier; it only orders the checklist. Also ignore
      length and polish as signals: longer, more detailed answers feel more right
      without being more right.

   b. **Citation check.** List every citation, link, statistic, name, and quote as a
      click-list for the human — these are the most-faked artifacts. Verify any that
      web search can confirm; mark the rest UNVERIFIED.

   c. **Premise check.** Re-read the original question the answer responded to. Did it
      contain assumptions the answer accepted without checking? Name them.

   d. **Math recomputation.** Recompute every number, total, percentage, and date
      calculation with code, not inspection. Flag discrepancies.

   e. **Fold test (advisory).** Note the claims most likely to flip under pushback —
      the ones resting on the answer's own authority rather than evidence.

   f. **Provenance and audience sweep.** Runs on every file in the envelope, at every
      tier. Start with whatever was assembled last — those files skipped the passes
      the main document got. This check is about *who the text is addressed to and
      which draft it came from*, not whether it is true.

      | Pass | Looking for | Where it shows up |
      |---|---|---|
      | **Audience** | Text addressed to someone other than the stated reader | "the submission", "the brief", "this document", "say so first", "note to self", "for the interview", "the honest sentence for…", risk rows whose mitigation is an instruction to the author |
      | **References** | IDs and pointers that don't resolve inside what's being sent | `INSIGHT-\d+`, `#\d+`, `Q\d+`, `G\d+`, "see §", "per `NN-name`", named artifacts held back as "available on request" |
      | **Draft residue** | Evidence of an earlier version showing through | `~~strikethrough~~`, TODO, TBD, FIXME, "largely resolved", "superseded", "revised after", "read this first" banners, changelogs, boilerplate blocks repeated across files |
      | **Tool tells** | Language describing an execution environment rather than a person working | "from this environment", "403", "not reachable", container or repo paths, "I ran", "the tool returned" |
      | **Third-party identifiers** | Real people quoted from public sources | `u/handle`, `@handle`, full names, emails, employer plus role. **Anonymize by default**; naming a private individual requires a stated reason that survives being read aloud to them |

      Grep for the patterns first, then read. Audience leakage frequently has no
      keyword — it is a sentence written in the author's planning voice that survived
      into the deliverable, and only a read catches it. Pay particular attention to
      first-person passages and to any table whose rows were written as working notes.

      **Consistency across files is part of this pass.** Where the main document and
      an appendix disagree — a figure, a name, an arm label, a decision that was
      reversed — the disagreement is a finding, and the one that was edited later is
      usually right. Say which.

3. **Report in this format:**

   **Findings** — table: claim / status (supported, unsupported, wrong, unverifiable) /
   evidence.

   **Premise issues** — anything the original question smuggled in, or "none found".

   **VERIFY BEFORE USE** — the human's short list: specific items, each with a
   ≤5-minute way to check it.

   **STRIP BEFORE SEND** — the output of 2f, as find-and-replace pairs: file /
   **exact quoted text, verbatim, so it can be searched for** / the replacement text,
   or `DELETE`. Never a direction like "reword this" or "consider removing" — the
   user should be able to work the table without rereading the document. Name every
   file the sweep covered, including the ones that came back clean. An empty result
   is a valid finding and is stated as such, with the file list beside it.

   **Bottom line** — one sentence: ship-shape after the checklist, needs rework, or
   don't use.

## Boundaries

- For your org's external content, also run its own fact-check skill if one is installed —
  it owns your canonical facts and wording; this skill owns general verification.
- If the user pushes back on a finding, hold it unless they provide new evidence —
  this skill folding under pressure would be its own punchline.
- **The 2f sweep is not tier-scaled and not optional.** Residue is cheap to remove
  and expensive to have found by the reader, so there is no stakes tier low enough
  to skip it.
- **Never report the sweep as clean without listing the files it covered.** "No
  issues found" over an unstated scope is the failure this check exists to prevent,
  reproduced by the check itself.
- The sweep reports; it does not silently fix. Residue sometimes encodes a real
  decision the author wants to keep — a visible reversal can be a strength when it
  is written for the reader rather than left over from writing. Quote it, say what
  it costs, and let the author choose.
