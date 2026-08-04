# ProjectFactory — Agent Evaluation Plan

Goal: make every agent in the pipeline **measurable**, so that (a) regressions are caught by numbers, not vibes, (b) provider/model swaps (frontier ↔ local) become data-driven decisions, and (c) the judge itself is proven trustworthy before its scores are trusted.

Guiding principles:

1. **The pyramid.** Cheap deterministic checks in large numbers → LLM-as-judge only where code can't decide → human labels as the calibration anchor (fewest, most valuable).
2. **Evaluate the evaluator first.** No judge score is meaningful until the judge passes consistency, sensitivity, and calibration tests.
3. **Blind pairwise + position swap** for any A/B comparison (LLM judges have position, length, and self-preference biases).
4. **Small honest sets over big noisy ones.** 10 well-chosen golden inputs beat 100 random ones; report stderr-style caveats, never over-read single runs.
5. **Seeded defects.** The cleanest test of any detector-agent is hiding a known flaw and measuring recall — the same instinct that caught the overfitting artifact in the trading pipeline.

---

## 1. Agent inventory & what each one gets measured on

The graph has 29 nodes in four families. Every node appears below.

### A. Control / routing nodes (deterministic evals — pure code asserts)

| Node | What to measure | Method | Metric |
|---|---|---|---|
| `orchestrator` | Intent routing correctness | **Golden intent set**: 60-100 real user messages (incl. past routing bugs: "tekrar yazar mısın" ≠ approve, off-topic input, rewrite/reopen shortcuts) → expected route | route accuracy; 100% on the regression subset |
| `decision_handler` | Action parsing (revise / approve / reopen / improve) | Golden set of decision messages incl. decorated "None"/"Yok", ambiguous phrasings | parse accuracy |
| `user_checkpoint` | HITL gate integrity | State-machine tests: pause → external input → resume with state intact; double-submit locked (`_pipeline_locks`) | pass/fail invariants |
| `doc_gate` | Gate transitions (PHASE_GATES) | Unit tests over allowed/blocked transitions | pass/fail |

*These are pytest suites — no LLM calls, run in CI on every commit.*

### B. Generative agents (structure asserts + judge rubrics + pairwise)

Common checks for **all** generative nodes:
- **Structure assert (code):** required sections present, format contract honored (e.g. `_ADJUSTMENTS_HEADING` contract), output length within band (the 60%-length regression guard, generalized).
- **Groundedness (judge):** claims consistent with the inputs the agent was given (brief, research docs); no invented facts.
- **Rubric score (judge, versioned):** role-specific rubric, evidence citation per deduction (existing `RUBRIC_VERSION` machinery).

Role-specific additions:

| Node | Extra checks |
|---|---|
| `idea_analyst` | Brief faithfully reflects the raw idea (no scope invention); parseable by `_extract_brief` |
| `market_researcher` | **Source-grounding**: every market claim traceable to a web-search result; freshness of sources |
| `competitor_analyst` | Named competitors actually exist (spot-check assert against search results); no hallucinated products |
| `tech_feasibility` | Recommendations consistent with brief's constraints; risk list non-empty for non-trivial ideas |
| `spec_writer` | Section completeness vs template; requirements traceable to research; no silent section drops (the truncation-bug guard) |
| `architecture_designer` | Components cover all spec requirements (coverage matrix check); tech choices justified |
| `ux_strategist` | Flows cover the personas/journeys named in spec |
| `gtm_strategist` | Channels/pricing consistent with market research numbers |
| `financial_modeler` | **Arithmetic asserts (code!)**: totals add up, margins computed correctly — LLM math is checkable with a script |
| `planning_agent` | Plan covers all spec deliverables; dependencies acyclic (code check) |
| `doc_formatter` | Deterministic formatting contract — snapshot tests, no judge needed |
| `brand_strategist` / `legal_advisor` / `visual_designer` / `design_system_architect` | Structure + groundedness + rubric; `legal_advisor` additionally: **must include "not legal advice" scope framing** (code assert) |
| `revise_document` / `spec_improver` | **Edit-quality trio**: (1) requested changes actually applied (judge, per-adjustment), (2) untouched sections preserved (diff-based code check), (3) no length collapse (code) — this is the "applied adjustments" bug class, made into a permanent test |

### C. Evaluator agents (meta-eval — evaluate the evaluator)

| Node | Test | Method | Metric |
|---|---|---|---|
| `quality_reviewer` (judge) | **Consistency** | Same doc scored 3× → spread | max spread ≤ agreed band (e.g. ±5) |
| | **Sensitivity** | Doc vs deliberately degraded doc | degraded scores strictly lower, gap ≥ threshold |
| | **Calibration** | Compare with human (owner) approve/revise decisions logged at HITL gates | agreement rate; disagreements reviewed monthly |
| `devils_advocate` | **Seeded-defect recall** | Inject known flaws (contradiction, missing section, unrealistic claim, broken dependency) into good docs → does DA flag them? | recall on seeded set; false-positive rate on clean docs |
| `consistency_checker` | **Seeded-inconsistency recall** | Cross-doc contradictions planted (spec vs research number mismatch, name drift) | recall / FP rate |
| `research_review`, `spec_review`, `quality_review` | Review-summary fidelity | Summary contains every blocking finding from underlying reviews (judge) | omission rate |
| `research_discussion`, `review_discussion` | Discussion-action fidelity | Golden conversations → expected `apply_discussion_action` outcomes; applied-adjustments memory honored on re-runs | action accuracy |

### D. End-to-end (pipeline level)

- **Golden ideas set:** 8-12 diverse project ideas (SaaS, game, marketplace, hardware-ish, non-profit…), fixed forever.
- Full pipeline run per configuration → final package evaluated by: structure asserts + frontier judge rubric + **blind pairwise vs baseline snapshot**.
- Operational metrics per run: total tokens, cost, wall-clock, # of DA/consistency iterations before approval, # of HITL interventions needed.

---

## 2. Shared infrastructure (build once)

1. `evals/` package in backend: golden sets as YAML/JSON fixtures, `eval_runner.py` (async, reuses provider layer), results as JSON under `evals/results/` with **run metadata** (model per role, rubric version, git sha, date) — same spirit as the trading pipeline's validation artifacts.
2. **Judge harness** with bias hygiene baked in: pairwise-with-swap helper, score-with-evidence schema, judge model always ≥ tier of judged model.
3. **Score history** extended from the existing regression tracking: every eval run appends; a simple report diffs vs last run and flags drops beyond stderr-ish noise band.
4. CI split: **Tier-0** (deterministic asserts, every commit, free) / **Tier-1** (judge evals, on demand / nightly, costs tokens) / **Tier-2** (full e2e + ablation, manual trigger).

---

## 3. Local-vs-frontier experiment (role ablation)

The clean design for "which roles can run on a local model without quality loss":

1. Baseline: full-frontier run over the golden ideas set → snapshot outputs.
2. **Swap exactly one role** to the local model (e.g. `spec_writer` → Qwen3.6-35B-A3B via Ollama provider), everything else frontier.
3. Full run → blind pairwise (frontier judge, position-swapped) against baseline + structure pass-rates + iteration counts.
4. Repeat per role family (researcher, spec roles, packaging roles, DA, judge — judge last and most carefully: it needs the meta-eval from §1C first).
5. Output: per-role verdict table — *local-OK / local-with-caveats / keep-frontier* — with numbers attached.

Expected shape of the result (hypothesis, to be tested, not assumed): formatting/packaging roles go local first; research needs tool-calling reliability; judge and DA stay frontier longest.

---

## 4. Step-by-step implementation order

Each step is small enough to land alone; the plan is deliberately incremental ("bir yandan yapmaya başlarız").

- **Step 0 — scaffolding** *(half a day)*: `evals/` package, runner skeleton, results schema, first golden-intents YAML. **STARTED**: `backend/evals/fixtures/golden_intents.yaml` landed — ~50 cases across 17 categories (regression cases from real bugs are one tag among many: ambiguity, multi-intent, negation, code-switching, injection, wrong-target traps, conditionals…). Remaining: wire `eval_runner.py` to the discussion-intent code path.
- **Step 1 — Tier-0 asserts** *(a day)*: orchestrator + decision_handler golden tests, doc_gate/user_checkpoint invariants, structure asserts for spec_writer + financial arithmetic checks. Wire into CI.
- **Step 2 — judge meta-eval** *(a day)*: consistency (3× scoring), sensitivity (degraded-doc pairs — write 3 degraded variants for 2 golden specs), calibration logging at HITL gates.
- **Step 3 — seeded defects** *(a day, fun)*: defect injector (5 defect types), DA + consistency_checker recall harness.
- **Step 4 — generative rubric evals** *(1-2 days)*: role rubrics for research trio + spec family + packaging family; edit-quality trio for revise/improve nodes.
- **Step 5 — e2e golden runs** *(a day)*: 8-12 golden ideas, baseline snapshots, operational metrics.
- **Step 6 — Ollama provider + role ablation** *(after local models are set up)*: the §3 experiment; publish the verdict table in README.
- **Step 7 — report & regression loop**: nightly-ish Tier-1, score-history diffs, README badge/table with latest numbers.

---

## 5. Honesty rules (non-negotiable)

- Never present judge scores without the judge having passed §1C.
- Always report set sizes; small-set results are "pattern evidence", not proof.
- Baselines are snapshotted and versioned; comparing across rubric versions is forbidden (rubric version is stamped — use it).
- Negative/boring results (e.g. "local judge failed calibration") get written down too — they are the most credible portfolio material.
