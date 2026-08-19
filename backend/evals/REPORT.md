# Local-vs-Frontier Agent Evaluation — Reports

## Phase 1 final (2026-08-05 evening): local discussion role at 90±1, above frontier

Seven measurement rounds on the 68-case set with qwen3:8b think-on:
82 → 79 → 87 → 84 → 91 → 85 → 90. The full stack (3-vote self-consistent
approve verification, a two-sided instruction-vs-question gate on revise, a
target-routing question with glossary, plus two product features — cross-phase
rewind and post-completion editing) settled into a **90±1 band vs frontier's
87**, with the safety invariant (zero wrong approvals, zero negation
inversions) holding across the final three rounds. Dev-set caveat applies as
always; a held-out set decides the general claim.

The oscillation itself was the main lesson: every one-sided policy phrasing
(strict or loose, in either verifier) swung the pendulum — misses on one side
returned as false-positives on the other. Two-sided policy statements plus
majority voting ended it. Remaining classes are explicitly parked for
distillation or feature work, not further prompt surgery: the "spec"→prd
mapping (2 cases), conditional branch-guessing (1), multi-document edits in
one message (1, needs multi-action support), and a ±2-3-case sampling noise
floor. One genuine contract bug was found on the way: the roadmap was missing
from the revise schema's allowed targets — the eval's three-round "model won't
act" signal was a schema prohibition.

---

# Report v1 (2026-08-05)

Goal: decide, **per agent role**, whether a local model (Ollama, 6 GB laptop
GPU) can replace the frontier API without quality loss. Two evals, six model
configurations, everything measured on the real code paths.

## Headline: the role × model matrix

| Config | Intent/discussion role (68 golden cases) | DA/consistency role (15 seeded defects) |
|---|---|---|
| Frontier (API + failover) | 87% | **77%** — obvious 100%, subtle 50%, FP 0 |
| **qwen3:8b, thinking on** | **85%** | 27%, plus trust failures |
| qwen3.6:35b, thinking on | 81% | ~50%, but 3/8 reports came back empty |
| qwen3:8b, thinking off | 75% (dangerous negation inversions) | — |
| qwen3.6:35b, thinking off | 63% (action-JSON discipline collapses) | — |
| deepseek-r1:7b | 51% | 3% |

**Decision (supported by this data):** the intent/discussion role can go local
today — qwen3:8b with thinking on is statistically level with frontier (58/68
vs 59/68). The adversarial-review roles (devil's advocate, consistency, judge)
stay on frontier: every local option is either far below the bar, unreliable,
or actively untrustworthy. "All roles local" becomes a staged migration, not a
switch flip.

## Eval 1 — Golden-intent set (what it is, what it found)

68 cases across 17 categories (5 languages, negation traps, prompt injection,
wrong-target traps, multi-intent…), run through the real discussion pipeline
(deterministic shortcuts + LLM action parsing + state application), scored by
observed state diff. Three frontier rounds first: 90% → 82% (after expanding
to 68 multilingual cases) → 87% (after prompt fixes the eval itself motivated:
six new intent rules + temperature 0.5→0.1 on intent-bearing calls).

Key findings:
- **Thinking mode is the safety switch for local models**: 8B jumps 75%→85%
  with thinking on, and its dangerous failure class (executing the *opposite*
  of "don't approve yet") disappears entirely.
- Deterministic layers hold everywhere: regex shortcuts (rewrite/reopen) and
  injection/off-topic handling scored 100% for every model, including the
  weakest — putting critical intents in code instead of prompts works.
- R1 thinks at length, then answers in prose instead of emitting the action
  JSON — wrong tool for a format-critical role.

## Eval 2 — Seeded defects (what it is, what it found)

Two fictional projects (fintech SaaS, logistics B2B), five realistic spec docs
each; 15 defects across 11 types planted as reviewable patches (contradictions,
fabricated evidence, impossible math, cross-doc mismatches, deleted privacy
sections, absurd targets…). Both directions measured: recall on defected
bundles, misstatement-only false positives on clean bundles. Human-judge
protocol pinned in `fixtures/seeded_defects/JUDGING.md`; full per-defect
scores in `JUDGE_SCORES.md`.

Key findings:
- **Frontier catches everything present-and-wrong (8/8 obvious) and misses
  half of what is absent or invented** (deleted compliance sections, fake
  pilot statistics). Absence-detection is the open ceiling — for frontier too.
- **qwen3:8b failed the trust bar, not just the score bar**: it fabricated a
  citation, used a planted fake pilot as supporting evidence twice, and
  certified a defect-riddled bundle as "fully consistent". A reviewer that
  invents evidence is worse than no reviewer.
- **qwen3.6:35b's problem is reliability, not judgment** — where it produced
  output its analysis approached frontier quality; 37% of its report calls
  returned empty (thinking consumed the entire generation budget).
- **"Reasoning model → good adversarial reviewer" was falsified** at this
  size: deepseek-r1:7b produced generic consulting boilerplate untethered
  from the documents (0.5/15) and misstated doc contents repeatedly.

## Infrastructure lessons (paid for in debugging time)

1. Ollama's OpenAI-compat endpoint ignores thinking control → native
   `/api/chat` with per-tier `think` (measured: empty replies otherwise).
2. Ollama's default ~4k `num_ctx` silently truncates long-prompt runs →
   explicit 16384 (measured: 35B report calls returned empty content because
   thinking never fit).
3. Provider failover changes classification behavior — intent flip-rate ~8%
   between frontier runs under rate-limit churn. Local models remove that
   noise source entirely.
4. Empty output is a finding: without `report_chars` in run metadata, 35B
   would have been misjudged as "bad" when the config was at fault.

## Next steps (each measurable with the harnesses already built)

1. DA/consistency prompt upgrade: explicit absence-scanning ("what critical
   section is missing?") and evidence-verification ("does every cited stat
   exist in the inputs?") duties → re-measure all configs; attacks frontier's
   own 50% subtle-recall ceiling too.
2. Intent-role hardening before local rollout: deterministic negation guard,
   few-shot examples for casual approvals, gate-target emphasis (the
   financial_model fixation) → re-measure 8B think-on.
3. 35B reliability engineering if its quality is wanted: retry-on-empty,
   larger `num_predict`, then re-judge.
4. Remaining role families (spec writers, judge meta-eval) per `EVAL_PLAN.md`
   steps 2 and 4.


---

# Phase 2 — Generator roles (spec documents)

Canonical judge report follows (working copy lives in results/generators/JUDGE.md,
raw generations in results/generators/<model>/ — unversioned).

## Judge report

Judge: Claude (frontier), reading full documents blind-ish (model label visible, scoring on content).
Date: 2026-08-06. **Development-set results** — same two fixture projects used throughout;
generalization claims require a held-out project set.

Method: fixed-context generation (all models generate from the SAME golden inputs — see
`gen_runner.py`). Deep-read sample: PRD + financial_model (invoicefox) and architecture
(fleetsense) for frontier/8B/35B; R1 deep-read on PRD only (grounding scan already
flagged it); 35B additionally skimmed on ux_design + gtm_strategy as leading local.

Scores are 1–5 per dimension: Grounding (uses fixture facts, no fabrication),
Depth (engineering/product judgment), Coherence (internal consistency incl. arithmetic),
Format (structure contract, no wrapper artifacts).

## Per-document findings

### invoicefox PRD
| Model | Grounding | Depth | Coherence | Format | Notes |
|---|---|---|---|---|---|
| frontier | 4 | 5 | 5 | 5 | 14 G/W/T stories, 3 personas, behavior-signal timing logic; risks section beyond template |
| qwen3-8b | 3 | 3 | 4 | 5 | Serviceable but thin (3 stories); **fabricated stat**: "$1.4B annually (per market research)" — not in fixtures |
| qwen3.6-35b | 5 | 4 | 5 | 5 | Best grounding density: fixture WTP band, competitor gaps, exact recommended stack + "6–10 weeks solo dev"; original per-client tone-memory feature; scope-discipline adjustment (phase memory to v2) |
| deepseek-r1-7b | 1 | 2 | 3 | 3 | Generic ("revolutionize..."), zero fixture numbers, wrapped in ```markdown fence |

### invoicefox financial_model
| Model | Grounding | Depth | Coherence | Format | Notes |
|---|---|---|---|---|---|
| frontier | 4 | 4 | 5 | 5 | Correct arithmetic throughout (150×$12=$1800 MRR ✓); conservative salaried-team assumption set; honest cash-negative Y1 |
| qwen3-8b | 3 | 3 | **1** | 5 | Arithmetic/logic riddled: invented payback formula ("12mo/1.42"), break-even 12,500 doesn't follow from own inputs, Q1 revenue contradicts own growth story, "lower price → LTV/CAC improves" inversion, wrong "per research" attributions |
| qwen3.6-35b | 5 | 5 | 5 | 5 | **Standout.** Consistent chain ARPU→margin→CAC→LTV; correct payback formula (CAC/margin=3.0mo); break-even 1800/10.65≈169 ✓; Q1 rev 65×11.5×3≈$2,243 ✓; transparent 50→30mo lifespan discount; grounded ($10–20 band, <$40 CAC, 8% conv, PRD 600-user cross-ref) |

### fleetsense architecture
| Model | Grounding | Depth | Coherence | Format | Notes |
|---|---|---|---|---|---|
| frontier | 5 | 5 | 5 | 5 | Service decomposition, Celery EOD aggregation, adaptive 5s ping, <30s solve target from fixture, optional OSRM for tile-cost cap |
| qwen3-8b | 3 | 2 | 3 | 4 | Generic diagram (Driver App → Data Storage direct edge), auth scheme inconsistent (API Key vs Firebase per endpoint), typo endpoint `/api/v/1/reports`, thin shapes |
| qwen3.6-35b | 5 | 5 | 5 | 5 | Near-parity with frontier; **privacy handling deeper than frontier's** (shift-scoped location masking, consent token, per-region audit); tile cache grounded in fixture cost concern; realistic API shapes |

### 35B skim — invoicefox ux_design, fleetsense gtm_strategy
Both strong. UX: mermaid flows with explicit error paths (bounce→backoff→Delivery Failed CTA),
behavior-aware escalation, tone-fatigue recovery prompt. GTM: channels grounded in fixtures
($8/van ROI framing, courier associations, leasing/insurance bundling), concrete milestones,
defines billing unit ("users" = active vans). No weak spots found in skim.

## Aggregates (structure scan, all 40 docs — from meta.json)
| Model | Headings full | Avg words | Avg secs | Grounding anchors (of 80) |
|---|---|---|---|---|
| frontier | 7/10 | 1536 | 9 | 34 |
| qwen3-8b think-on | 10/10 | 730 | 292 | 32 |
| qwen3.6-35b think-on | 9/10 | 886 | 210 | 29 |
| deepseek-r1-7b | 10/10 | 691 | 91 | 19 |

(Frontier's 7/10 = long-doc heading drift, not content gaps; 2 docs over word limits.
35B's one weak doc: fleetsense financial_model, 343w — not deep-read; flagged for spot-check
if 35B is adopted for financial role.)

## Verdict (development set)

- **qwen3.6:35b is migration-ready for generator roles** on this dev set: PRD/architecture at
  or near frontier parity, financial_model arguably the best single document in the eval
  (only model with a fully consistent numeric chain using correct formulas). One caveat:
  its fleetsense financial (343w) was short — verify before relying on the financial role.
- **qwen3-8b is NOT suitable for financial_model** (coherence 1 — multi-step arithmetic
  failures, consistent with its known small-model numeric weakness) and is weak for
  architecture (depth 2). Passable for PRD-class docs with a fabrication risk
  (invented "$1.4B (per market research)" citation — repeats its known pattern).
- **deepseek-r1-7b is unsuitable for generation**: fastest (91s avg) but generic content
  (19/80 anchors), no fixture grounding, format artifacts (markdown fences).
- **frontier remains best for breadth/depth** (PRD story coverage) but 35B's grounding
  density matches or exceeds it; the quality gap no longer justifies API cost for these roles
  on this dev set.

## Addendum — financial-role recheck at 8192 tokens (2026-08-06)

The weak 35B fleetsense financial (343w, truncated mid-sentence, 4/6 headings) was
hypothesized to be a token-cap artifact (max_tokens=6144 shared with thinking budget).
Recheck: both financial docs regenerated on 35B with GEN_MAX_TOKENS=8192
(`results/generators/qwen3.6-35b_think-on_8k/`).

Result: **hypothesis confirmed.** Both docs now 6/6 headings, ~850-890w, no truncation.
Arithmetic audit:
- fleetsense: quarterly table fully self-consistent (65×16×$8=$8,320 MRR ✓, COGS/GP/Net
  all verify), correct payback formula (240/84≈3.0), break-even 14,000/6.40≈2,190 ✓.
  Minor nits: GM stated 70% in unit econ vs 25% COGS (75%) in projection; "Monthly LTV"
  mislabel; best-case sensitivity row doesn't back out exactly. Nits, not the 8B error class.
- invoicefox: entire chain verifies (LTV 10.80×0.75/0.035≈$231 ✓, payback 48/8.10≈5.9 ✓,
  break-even 5,800/9.20≈630 ✓, quarterly revenue/GP/net all recompute ✓). Also shows real
  product judgment: flags free-tier cap (5 invoices) as misaligned with fixture behavior
  data (3–8 invoices/mo) — an insight none of the other models surfaced.

Conclusion: 35B financial weakness was an infra setting, not model capability.
**Financial role: raise generation max_tokens to 8192 and route to 35B.**

**Adopted role routing (user decision 2026-08-06; held-out validation still open):**
`LLM_ROLE_PROVIDERS=...,spec=ollama:quality` + `LLM_ROLE_THINK=...,spec=on`, generation
max_tokens raised 6144→8192 (specification.py). Original recommendation:
all five spec generator roles → qwen3.6:35b (think-on); keep frontier as fallback chain.
Latency note: 35B averages 210s/doc vs frontier 9s — acceptable for offline document
generation, relevant if UX expects fast turnaround.


---

# Phase 3 — Decomposed Devil's Advocate (quality roles)

The monolithic "criticize everything" DA was the measured weak spot of local
models (8B 27% with trust violations; 35B ~50% unstable; frontier 77%
pre-upgrade). Phase 3 decomposed it into SIX micro-passes ordered by
verifiability, each built on the same skeleton: narrow LLM extraction →
code-side validation (verbatim-quote grounding, number grounding) → narrow
verification questions with 3-vote majority → deterministic composition
(no synthesis call; every finding carries its evidence).

| Pass | Owns | Mechanism | Model |
|---|---|---|---|
| numeric | arithmetic, impossible-math | LLM converts claims to expressions; Python (ast safe_eval) verdicts | 8B |
| evidence | fabricated first-party evidence | extract → completed-claim gate → per-claim support check vs bundle | 8B |
| absence | missing-critical sections | short checklist; applicability gate; presence votes must quote | 8B |
| consistency | cross-doc value drift | fact rows → unit-family pairing (code) → derivation guard (code) → same-quantity vote | 8B |
| scope | out-of-scope references | PRD exclusion list → per-(feature×doc) presence vote with proof quote | 8B |
| critique | contradictions, infeasibility, absurd targets, audience | per-doc candidates → two-sided genuineness judge, majority | 35B gen+judge, repeats=2 |

Dev-set results (15 seeded defects, clean bundles for FP): single-run recall
~11-13/15 with 0-2 clean FPs; parked after exhaustive measurement: A4
(context-established identities — six configurations tried) and A1-class
single-run variance. Key measured lessons: the fast model is reliable at
narrow-factual questions and unusable for evaluative judgment in ANY prompt
framing (the boundary that routes critique to the quality model); one-sided
verifier policies oscillate (reproduced twice; two-sided + majority is the
cure, again); worked examples beat abstract rules, but example content must
be decontaminated from fixtures (caught once by the user) and example
patterns silently define coverage.

## Held-out verdict (sealed single shot, 2026-08-08, config @ e041e5e)

Two unseen domains (consumer edtech with minors; P2P equipment marketplace),
15 fresh defects mirroring the dev distribution. Result:

- **Recall 11-12/15 — no drop from the dev band.** Hits spread across all
  six passes, including the scope pass added the day before (C7 caught with
  proof quote). At the frontier monolithic baseline (77%) with a fully
  local runtime.
- **Clean-bundle FPs rose to 9** (dev band: 0-2). Clustered causes, all now
  known-issue backlog: numeric cross-line chains picking wrong partners (a
  measured cost of the revenue-chain worked example), degenerate same-quote
  consistency pairs (a code gap dev's short docs never triggered), critique
  judge noise. Precision guards were dev-calibrated; recall architecture
  generalizes.
- Misses: C8 absurd-target (the most resistant class on dev too), D5
  take-rate pair (consistency sampling), D6 (partly a fixture-authoring
  flaw — the seeded removal left waiver traces in other docs).

Verdict: the decomposition thesis holds — catch capability generalizes;
FP hardening continues on dev (this held-out set is retired for the
precision-affected classes per HELDOUT.md). Durable fixes for parked
classes and judge variance are Phase 4 distillation targets.

# Phase 4 — Judge distillation (critique genuineness judge)

Goal: train the critique pass's genuineness judge ("is this candidate
finding a real defect?") into Qwen3-8B so the pass can drop from the 35B.
Data: 19-project synthetic corpus (self-labeled seeded defects), 774
candidates labeled 126 genuine / 648 not (95 by code via seeded-quote
overlap, 679 by teacher Opus over chat; meta-eval passed 10/10 reject +
8/8 accept). SFT set: 600 train / 174 eval, project-disjoint split
(eval: mendhub/plantpulse/recitehall/tastetrail), production judge prompt
verbatim, rationale-first JSON. All numbers below are on the sealed
174-row eval (30 genuine).

## Run #1 failure: yes-sayer collapse from rationale STYLE

| config | P | R | note |
|---|---|---|---|
| base Qwen3-8B (Colab, untuned) | 0.24 | 0.67 | half yes-machine baseline |
| tuned run #1 | 0.22 | 0.97 | ~132 positives of 174 |

Root cause (verified: 19/30 sampled answers opened with the template):
all 95 code-labeled genuines shared ONE rationale template ("The quoted
text is a real defect..."), so rationale style became a proxy for the
label — in rationale-first format the opening phrase locks the verdict
to true. META-LESSON: every part of a training example is signal,
including style; style must be i.i.d. with respect to the label.

Fix (single-variable): the 95 rationales rewritten by the teacher
(decontaminated export→import, `fix_rationales.py`); new set has the
template 0 times, 90 distinct openings across 96 train genuines;
split/counts byte-identical otherwise.

## Base-candidate shootout (zero-shot, Ollama, same eval)

Community bases with post-training claims, tested before retraining:
hermes3:8b P0.15/R0.13 (reject-machine), selene-mini:8b (a dedicated
judge model!) P0.17/R0.90 and tulu3:8b (reasoning-RL) P0.18/R0.97 (both
yes-machines). None beat base Qwen3-8B → base stays; "even judge-tuned
models collapse on our distribution" = the distribution-mismatch thesis,
now measured. Details in `distill/BASE_CANDIDATES.md`.

## Run #2 (clean rationales): collapse cured, 35B profile reached

| category | P | R | n |
|---|---|---|---|
| TOTAL | 0.62 | 0.33 | 174 |
| absurd-target | 1.00 | 0.75 | 7 |
| audience-mismatch | 0.33 | 0.33 | 22 |
| infeasible-plan | 1.00 | 0.60 | 41 |
| infeasible-tech | 0.50 | 0.67 | 27 |
| internal-contradiction | 0.33 | 0.07 | 77 |

Same data counts, only rationale style changed: P 0.22→0.62, R 0.97→0.33.
The template diagnosis is confirmed by measurement. absurd-target (a
named distillation target) went from hardest-for-extractor to 1.00/0.75.
The tuned 8B now sits at the production 35B judge's profile (below) —
matching recall, lower precision — but does not beat it.

## Zero-shot ladder: the production judge measured, and a new contender

First-ever measurement of the production critique judge (qwen3.6:35b) on
this distribution, plus qwen3.8:27b (released 2026-08-14), both via
`zero_shot_eval.py` (think off, temp 0):

| model | P | R | note |
|---|---|---|---|
| tuned-8B run #2 | 0.62 | 0.33 | ~5GB |
| qwen3.6:35b (production judge) | 0.82 | 0.30 | 23GB; audience-mismatch 0.00/0.00 |
| qwen3.8:27b zero-shot | 1.00 | 0.57 | 18GB, ~4.4s/row vs 35B 7.5s |

27B truncation check: the first run's 220-token cap cut 29/174 replies
before the JSON verdict; a num_predict=512 rerun dropped unparsed to 7
and left the verdict unchanged (tp=16 fp=0 fn=12 tn=139; R=0.57 over
parsed rows, 0.53 worst-case counting the 2 unparsed genuines as
misses). Zero false positives across all 174 rows in both runs.

Readings: (1) the production 35B judge is weak on this distribution —
misses 70% of genuines and catches ZERO audience-mismatch; Phase 4's
premise is now quantified. (2) 27B zero-shot dominates both the 35B and
the tuned student on every axis, at zero FP. (3) internal-contradiction
is weak across ALL models (27B R0.27, tuned R0.07, 35B R0.33) — the
largest class (77 rows); label quality there intersects the known
35B-generator cross-line reconciliation errors and deserves an audit.

## 27B in the real pipeline: dev critique gate PASSED

`micro_runner --pass critique` on dev, production config (gen+judge on
the candidate, samples=3, repeats=2), label `qwen3.8-27b-ens2`, vs the
frozen 35B config (`qwen3.6-35b-ens2`):

| run | 35B-ens2 | 27B-ens2 |
|---|---|---|
| invoicefox defected | 3 findings | 6 findings, in-scope 3/3 |
| invoicefox clean | 0 FP | 0 FP (14→6 judge filtering) |
| fleetsense defected | 7 findings | 4 findings, in-scope 3/3 |
| fleetsense clean | 1 FP | 0 FP |

27B catches all 6 in-scope critique defects with ZERO clean-bundle FPs
(35B: 1). Its extra defected-bundle findings are not noise: e.g. it
flagged fleetsense's churn math (10% monthly churn stated as ~33-month
average lifetime), a real pre-existing flaw the 35B never surfaced.
Cost: slower wall-clock (defected combos 17-22 min vs 35B's shorter
runs; clean combos 4-7 min).

Measurement integrity note: the first four "27B" runs were invalid and
deleted — micro_runner's critique defaults (`CRITIQUE_JUDGE_TIER=2`,
gen_tier=2) silently routed both roles to the FAST model, so the runs
measured 8B gen+judge under a 27B label. The flood they showed (17→15
candidates passing) was the known 8B judge indiscrimination, consistent
with Phase 3. Lesson repeated: pin EVERY tier explicitly when the
harness has per-stage env defaults.

Production routing: DONE. `OLLAMA_MODEL_CRITIQUE` splits the critique
pass (gen + judge) from the shared quality-model knob so the five
Phase-2-validated spec generators are untouched; the dev .env now pins
the critique to qwen3.8:27b.

## 27B as spec generator: blocked by hardware, not measured on merit

The gen_runner eval (dev, think-on, both tiers pinned to 27B) produced
FOUR 900-second timeouts with zero output — no document completed.
Root cause, verified: qwen3.8-27b is a DENSE 27.3B (`ollama show`:
arch qwen35), while qwen3.6:35b is MoE (arch qwen35moe, small active
set — why it manages ~210s/doc on CPU). On this machine (RTX 3060
Laptop, 6GB VRAM) the dense 19GB model runs 87%/13% CPU/GPU at 16k
context; a trivial 200-token call took 47s, so an 8k-token spec
document is arithmetic-infeasible inside any sane timeout. Verdict:
generator roles stay on the 35B; the 27B-as-generator question is OPEN
pending better hardware, not answered. (The critique role is unaffected:
short generations, measured 4-22 min per full review, dev gate passed.)
Infra lesson: model quality rankings do not transfer across roles when
the roles have different output-length profiles and the hardware is
CPU-bound — architecture (MoE vs dense) can dominate parameter count.

Tuned-8B GGUF export parked; base change for a possible run #3 is a
27B-vs-8B-class question per the BASE_CANDIDATES protocol.
