# Seeded-Defect Eval — Judge Scores

Judge: Claude, per `fixtures/seeded_defects/JUDGING.md`. Union recall = a defect
counts if EITHER agent's report identifies it (per-agent noted). Ambiguity
resolves downward.

## Known benign findings in the CLEAN fixtures (not FPs — real, unplanted)

Discovered during frontier judging; any model flagging these on clean bundles
gets credit as a correct catch, NOT a false positive:

1. InvoiceFox: PRD churn target (<2% after m3) vs Financial Model assumption
   (~8% early → <5%) — genuine tension.
2. InvoiceFox: "basic analytics" in PRD v1 scope has no architecture component.
3. FleetSense: PRD's one-tap "delayed" flag missing from the UX driver flow list.
4. FleetSense: PRD's owner-visible location-audit-log absent from architecture.

---

## FRONTIER (Gemini-flash via failover) — judged 2026-08-05

### Recall (defected bundles) — union 11.5/15 (77%)

| Defect | Type | Severity | Score | Caught by | Note |
|---|---|---|---|---|---|
| A1 free-limit contradiction | internal-contradiction | obvious | HIT | both | explicit |
| A2 fabricated beta | fabricated-evidence | subtle | **PARTIAL** | da | doubts the 34% *holding at scale*; never questions that the beta itself is invented |
| A3 LTV:CAC math | arithmetic | obvious | HIT | both | full math worked (0.87:1) |
| A4 ARPU $19 vs $12 | cross-doc | subtle | HIT | both | |
| A5 in-browser 7B finetune | infeasible-tech | obvious | HIT | both | "absurdity" |
| A6 privacy section removed | missing-critical | subtle | **MISS** | — | absence not noticed |
| A7 workspace out-of-scope | out-of-scope-ref | subtle | HIT | both | |
| A8 10M users / $500 | absurd-target | obvious | HIT | both | opener of the DA report |
| B1 offline vs live tracking | internal-contradiction | obvious | HIT | both | |
| B2 fabricated pilot | fabricated-evidence | subtle | **MISS** | — | 14-fleet/31% never questioned |
| B3 churn math impossible | impossible-math | obvious | HIT | both | 28% retention derived correctly |
| B4 CLI-only for non-tech | audience-mismatch | obvious | HIT | both | |
| B5 $15 vs $8 pricing | cross-doc | subtle | HIT | both | |
| B6 driver consent removed | missing-critical | subtle | **MISS** | — | absence not noticed (clean-run consistency DID reference privacy — the defected run didn't miss-and-mention) |
| B7 solo 6 microservices/6wk | infeasible-plan | obvious | HIT | da | "timeline fantasy" |

**By severity: obvious 8/8 (100%) · subtle 3.5/7 (50%).**
**Failure pattern: ALL misses are absence/fabrication classes** — what's present
and wrong gets caught; what's missing, or confidently invented, sails through.

### False positives (clean bundles): 0 across 4 reports
Clean-bundle findings were either legitimate opinion/risk-raising or correct
catches of the known benign fixture findings (all 4 of which frontier's
consistency reports found — fixture-validation bonus).

### Qualitative
Reports well-structured: mitigations everywhere, RISK grade present,
Recommended Adjustments honest and numbered. DA voice appropriately adversarial
without fabricating.

---

## QWEN3.6-35B think-on (num_ctx=16384) — judged 2026-08-05

**Reliability failure first: 3/8 reports EMPTY, 1 truncated mid-sentence**
(thinking sometimes consumes the entire generation; nondeterministic).
Recall scored on available reports only.

### Recall — 7.5/15 (50%) *(with 1 defected report missing, 1 truncated)*
- HIT: A3 (full recompute), A4, A5, A7, A8 (opens with it, worked math), B1
  ("fatal contradiction", caught by BOTH agents), B5
- PARTIAL: B7 (flags 6-week timeline vs GTM mismatch; misses solo-engineer
  microservices infeasibility)
- MISS: A1, A2, A6, B2 (adopts the fabricated pilot as real), B3, B4, B6
- Same blind spots as frontier (absence + fabrication classes) plus A1/B3.
**Where it writes, quality approaches frontier. Its problem is reliability,
not judgment. Unusable in production until empty-output instability is fixed.**

## QWEN3-8B think-on — judged 2026-08-05

### Recall — 4/15 (27%)
- HIT: A3, A4 (both via consistency), A7
- PARTIAL: A5 (calls WASM-7B "unproven" but treats it as a differentiator to
  KEEP), B4 (adoption-risk framing only; suggests adding voice commands)
- MISS: everything else — including A8 (10M/$500, the most obvious defect)
### Trust failures (worse than the score)
- **Fabricated citation** in a defected DA report ("a 2023 study found 35%...")
- **Adopted the fabricated 14-fleet pilot as real evidence, twice**
- **Certified the defected FleetSense bundle as fully consistent** ("None — the
  documents are consistent"), calling the planted 31% figure "consistent"
- Contradictory footer in every DA report (3 adjustments + "None — holds up")
### Clean-bundle FP: 0 fabrications spotted in sampled clean reports

## DEEPSEEK-R1-7B — judged 2026-08-05

### Recall — 0.5/15 (3%)
- PARTIAL: B1 (challenges the offline-first sentence, never connects it to
  live tracking)
- Everything else MISS. Reports are generic risk-consulting boilerplate,
  disconnected from document specifics.
### Trust failures
- Misstates docs repeatedly: criticizes "cron-based scheduling" (docs say
  explicitly NOT cron), garbles pricing ("Free: $12/month"), invents a
  "predictive maintenance only in architecture" inconsistency (it's a PRD
  out-of-scope item), certifies defected numbers as "Clean".
**Hypothesis "reasoning model → good adversarial reviewer" is FALSIFIED for
this model/size: long thinking produced generic output, not document-grounded
critique.**

---

## COMBINED ROLE × MODEL MATRIX (both evals)

| Config | Intent role (68 cases) | DA/Consistency role (15 defects) |
|---|---|---|
| Frontier | 87% | **77%** — obvious 100%, subtle 50%, FP 0 |
| qwen3:8b think-on | **85%** | 27% + trust failures |
| qwen3.6:35b think-on | 81% | ~50% but 37% empty-output rate |
| deepseek-r1:7b | 51% | 3% |

---

# V2 — after the DA/consistency prompt upgrade (judged 2026-08-05)

Prompt changes measured here: DA gained §6 "What's MISSING" (absence scan) and
§7 "Evidence Audit" (incl. the never-echo rule); consistency gained "Derived
numbers" (recompute) and the "clean is a claim" rule.

## ⚠️ In-sample caveat (non-negotiable)

These prompts were written LOOKING AT the 15 defects' failure classes. Every
v2 recall number below is therefore a **development-set** result — inflated by
construction. General claims require the held-out defect set (Phase 3 of
LOCAL_MIGRATION_PLAN.md). The honest reading: "the upgrade closes the targeted
classes on the set that motivated it."

## Recall v1 → v2 (union, same 15 defects)

| Config | v1 | v2 | What changed |
|---|---|---|---|
| Frontier | 77% | **100% (15/15)** | Evidence Audit nails both fabrications ("a beta that has not occurred based on its own timeline is a fabricated metric"); §6 catches both removed sections |
| qwen3-8b think-on | 27% | **57% (8.5/15)** | Fabricated stats now flagged as untraceable instead of ADOPTED; both removed sections caught via §6; consistency now recomputes derived numbers and flags the price mismatch it previously certified as consistent |
| qwen3.6-35b think-on | ~50% partial | partial again (1 empty, 1 short) | empty-output retry landed after this chain; re-run pending |
| deepseek-r1-7b | 3% | not fully judged | eliminated for this role; spot-checks show same boilerplate pattern |

## Trust-failure follow-up (8B)

- Fabricated citation: none observed in v2 reports read
- Fake-evidence adoption: **cured** — "source is not traceable... fabricated
  numbers could undermine credibility"
- Wrong "clean" certification: **cured** on FleetSense numbers (price mismatch
  now Critical) — but B3 churn-math still verified-as-correct (recomputed LTV
  from the broken lifetime without checking churn→lifetime)
- Contradictory footer ("3 adjustments + None — holds up") **persists** — an
  output-format bug worth a deterministic post-process fix

## Clean-bundle FP check (v2, frontier sampled)

No fabrications or false conflicts in the sampled clean reports; the new
suspicion shows up as legitimate "no source cited" critiques (true statements).
Over-suspicion cost: none observed in sample.

---

**Verdict: role-dependent assignment is confirmed by data.** The intent role
can go local (8B think-on) at near-frontier quality; the adversarial-review
roles cannot yet — frontier stays for DA/consistency/judge until either 35B's
reliability is engineered around or prompts/models improve. Next fix candidates:
(a) DA prompt additions for absence-scanning and evidence-verification (attacks
frontier's own 50% subtle-recall ceiling too), (b) 35B empty-output mitigation
(retry-on-empty; larger num_predict), (c) re-measure.
