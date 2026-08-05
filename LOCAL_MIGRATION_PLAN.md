# Full-Local Migration Plan

**Decision (2026-08-05):** migrate ProjectFactory's runtime to local models
(Ollama), role by role, gated by evals. The frontier API remains available
**offline only** — as evaluation judge and distillation teacher — never in the
user-facing runtime path once a role has migrated. User data privacy is
preserved either way; development learns from frontier, production runs local.

Baseline measurements that shaped this plan: `backend/evals/REPORT.md`
(role × model matrix v1).

## Principles

1. **Eval-gated migration.** No role flips to local until it clears its bar on
   the measuring harness — and final judgment uses **held-out** fixtures the
   development loop never saw (Goodhart protection; the trading-pipeline
   lesson applied to ourselves).
2. **Verifier-first decomposition.** Anything checkable moves to code
   (arithmetic, source-matching, checklists); LLM calls get narrow,
   well-specified tasks; open-ended judgment is minimized and isolated.
   (Literature: candidate-scaling gains plateau at verifier precision.)
3. **Two temperature regimes.** Decision calls: temp≈0.1, single shot.
   Ensemble calls: temp≈0.8 × N samples + vote (self-consistency needs
   diversity). Never mixed up.
4. **Reliability is first-class.** Empty-output retries, parse retries,
   generous num_ctx/num_predict, timeouts — measured failure modes, not
   afterthoughts.
5. **The matrix is a living document.** New local models appear monthly;
   re-measuring is one command per harness.

## Phases

- **Phase 0 — Infrastructure** *(in progress)*: per-role model routing
  (role → provider/think map in config, force > role-pref > default order,
  prefer-with-fallback + fallback logging), empty-output retry in the Ollama
  path, deterministic Tier-0 intent tests in CI (LLM-free), `eval` make
  target for the full 68-case local run (local machines only — CI runners
  have no GPU).
- **Phase 1 — Ready roles**: intent hardening trio (deterministic negation
  guard in code, few-shot examples for casual approvals, gate-target
  emphasis) → re-measure 8B-think-on (bar: ≥85% and zero
  dangerous-inversion failures) → flip `discussion` role to local.
  Lightweight summary/format calls follow, gated by structure asserts.
- **Phase 2 — Generator roles**: build the spec-writer harness (golden
  briefs → docs → structure asserts + frontier judge + blind pairwise),
  measure 8B/35B/R1. Hypothesis to test, not assume: 35B shines at
  long-form generation. Migrate per doc-type as measurements allow.
- **Phase 3 — Quality roles (decomposed-DA experiment)**: micro-passes
  ordered by verifiability — numeric audit (Python, exact), evidence-source
  matching (semi-code), checklist absence scan (narrow yes/no+quote),
  cross-doc contradiction pairs, one open-ended critique pass — merged via
  universal self-consistency into the DA report format. Develop against the
  15 known defects; judge on a NEW held-out defect set vs the frontier
  baseline (77%). Publish the result either way.
- **Phase 4 — Distillation**: synthetic project/report generation (fixture
  machinery exists) → frontier traces → per-role LoRA (Unsloth/Colab) →
  re-measure. The judge role migrates only after passing its meta-eval
  (consistency / sensitivity / calibration).
- **Phase 5 — Fully Local Mode**: single config switch, honest quality
  banner where applicable, phase-based model batching (avoid 8B↔35B swap
  thrash on 6 GB), REPORT v3 with the full migration story in numbers.

## Architecture revision (2026-08-05): semantic verification over keyword overrides

First Phase-1 attempt used keyword layers (regex negation guard grown per eval
failure, alias-based target override). Rejected on review: meaning is expressed
in unbounded ways, pattern lists are brittle, and patterns derived from eval
fixtures are eval-overfitting by construction. Replacement design:

- **Narrow semantic verification** (`verify_discussion_action`): before a
  state-changing action applies, one narrow question — "is this an EXPLICIT
  approval? yes/no", "which document does this change belong to?
  (multiple-choice, the gated doc is the default)". This exploits the measured
  asymmetry: small models are weak at broad open-ended action parsing (27-51%)
  but near-frontier on narrow well-specified questions (85%+). Local inference
  makes the second call free.
- The negation regex remains only as a **frozen veto seatbelt** (asymmetric
  failure cost: a missed pattern = no worse than before; a false block = minor
  friction). It is not grown per eval failure.
- **Confirmation-card UX** for chat-initiated approvals is the third layer
  (frontend work, queued): the HITL architecture is itself the strongest guard.
- The durable fix remains **distillation** (Phase 4): teach the behavior
  instead of fencing it.

## Hardware honesty

On the current 6 GB-VRAM machine, 35B stays hybrid and slow and shows
empty-output instability under thinking load; the plan therefore leans on
**8B + code + ensembles**. Larger-memory hardware would widen Phase 2-3
options; the plan does not depend on it.

## Priorities

Phase 0 → 1 first (production win, decided 2026-08-05). Phase 3 is the
research flagship, started only after 0-1 land. Work is sliced into
interruptible half-day packages — the job-search process takes precedence
whenever it calls.
