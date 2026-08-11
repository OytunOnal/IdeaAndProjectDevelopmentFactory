# External fixture-set authoring brief

Paste everything below the line into a chat session with a model from a
DIFFERENT family than the one that built the system under test (DeepSeek,
Gemini, GPT, …). The author must not be the system's author — that is the
entire point of this document.

Two modes exist. Run them as separate sessions, producing separate sets:

- **natural** — the author knows nothing about how the reviewer works. Measures
  real-world recall; comparable to earlier sets.
- **adversarial** — the author is told what the reviewer checks and tries to
  slip past it. Finds structural blind spots; NOT comparable to earlier sets.

For adversarial mode, append the "System under test" section at the bottom.

---

## Task

You are authoring an evaluation fixture set for a document-review system. You
will write TWO fictional software product projects, each with five
specification documents, then plant defects into copies of those documents.
The system being tested has never seen your projects; its authors will only
read aggregate scores, not your documents, so the ground truth you record
must be complete and precise.

### Step 1 — two projects

Pick two product domains that are ordinary but not overlapping with each
other. Avoid these domains, which earlier sets already used: freelancer
invoicing, delivery-fleet routing, tutoring for minors, peer-to-peer
equipment rental.

For each project write five markdown documents, roughly 200-300 words each:

1. `prd.md` — problem, target users, core features (v1), pricing, in/out of
   scope, one section covering whatever obligation the product creates
   (privacy, consent, liability, safety — whichever genuinely applies),
   success metrics
2. `architecture.md` — stack, components, data flow, non-functional notes,
   team and timeline
3. `ux_design.md` — design philosophy, critical flows, key screens,
   interaction notes
4. `gtm_strategy.md` — positioning, launch phases, acquisition channels,
   targets
5. `financial_model.md` — pricing mechanics, 12-month projection, unit
   economics (ARPU, CAC, LTV, churn), break-even, funding

Hard requirement: **the numbers must be internally consistent and correct.**
If the model states LTV, it must follow from the ARPU, margin, and churn it
also states. If it states a break-even user count, it must follow from the
fixed costs and contribution it also states. These clean documents are the
false-positive control; any accidental error in them corrupts the
measurement. Do the arithmetic explicitly before writing the number.

### Step 2 — plant 15 defects

Produce a `manifest.yaml` listing 15 defects across the two projects, each a
minimal find/replace patch against a clean document. Format:

```yaml
- id: E1-short-slug
  project: <project folder name>
  doc: prd            # prd | architecture | ux_design | gtm_strategy | financial_model
  type: <defect class>
  severity: obvious   # obvious | subtle
  patch:
    find: "<text copied VERBATIM from the clean document — must appear exactly once>"
    replace: "<the flawed replacement, or empty string to delete a section>"
  detection: <one sentence: what a reviewer must substantively identify to score a hit>
```

Constraints:

- `find` must match its document **exactly once**, character for character.
- Change as little as possible — one sentence or one number where you can.
- Defects must be written in the document's own confident tone. No winking,
  no hedging that gives them away.
- When you delete a section, delete every trace of it. If other documents
  still reference the deleted obligation, the defect is not a clean removal —
  either remove those traces too or pick a different defect.
- Aim for roughly half obvious, half subtle.

### Step 3 — defect classes: use your own judgement

Earlier sets covered these classes, and repeating them teaches nothing new:
internal contradiction, arithmetic error, fabricated first-party evidence,
cross-document value conflict, missing critical section, out-of-scope
feature, absurd target, audience mismatch, infeasible plan, infeasible
technology.

**At least six of your fifteen defects must belong to classes NOT in that
list.** Invent them. What can be wrong with a set of product documents that
the list above does not name? Think about what a competent reviewer would
catch that a checklist would miss. Record whatever class name you choose in
the `type` field.

Additionally, include **three deliberate traps** — passages in the CLEAN
documents (not the defected copies) that look like defects but are
defensible on a careful read: an unusual-but-correct calculation, a design
choice that seems to contradict the audience until you read the rationale,
an apparent inconsistency that a nearby sentence resolves. List these
separately in `traps.yaml` with the same shape minus `patch`, plus a
`why_defensible` line. They are scored inversely: flagging one is an error.

### Step 4 — deliver

Output, in order, as separate labeled code blocks:

1. the ten clean documents (project name + filename before each)
2. `manifest.yaml`
3. `traps.yaml`

Do not summarize, explain, or comment on your choices outside these blocks.
Verify each `find` string against your own document text before you finish.

---

## System under test — APPEND ONLY FOR ADVERSARIAL MODE

The reviewer runs six passes. Design defects that survive all of them:

1. **Numeric audit** — a small model converts stated computations into
   arithmetic expressions; Python evaluates them and flags mismatches beyond
   20% relative tolerance. Only claims whose inputs appear in the document
   are checked.
2. **Evidence audit** — extracts first-party empirical claims (a pilot, beta,
   or test that supposedly already produced results) and checks whether any
   other document states that the event occurred.
3. **Absence scan** — a short checklist (privacy/data protection;
   consent/liability/safety) gated by an applicability question, then a
   presence question over the spec documents that requires a quote.
4. **Cross-document consistency** — extracts quantitative facts as
   (concept, value, unit), pairs same-unit facts whose values disagree,
   discards pairs where one value is a stated multiple of the other, then
   asks whether the pair refers to the same quantity.
5. **Scope echo** — extracts the PRD's explicit v1 exclusion list, then asks
   whether any other document specifies an excluded feature.
6. **Open critique** — a broad per-document pass looking for internal
   contradictions, infeasible technology, absurd targets, audience
   mismatches, and infeasible plans; every candidate must survive a
   two-sided genuineness vote by a larger model.

Every finding must carry a verbatim quote from the document or it is
discarded.
