# Held-out set — seal protocol

This set exists so that dev-set results (which prompts WERE iterated against)
can be checked for Goodhart overfitting. Its value is destroyed the moment it
is used for tuning. Rules:

1. **No iteration against this set.** Prompts, verifier policies, model
   choices, and generation parameters are frozen BEFORE a held-out run and
   are not modified in response to held-out results. If a held-out run reveals
   a fixable weakness, the fix is developed on the DEV set (or new dev
   fixtures) and the held-out set is retired for that role — a fresh held-out
   set must be authored for the re-test.
2. **One run per candidate configuration.** A "candidate" is a frozen
   (model, prompt, params) triple that already cleared its dev-set bar.
   Repeated held-out runs of the same candidate to "confirm" a better number
   are p-hacking; the first run's number is the number.
3. **Every exposure is logged below** — date, role, configuration, purpose —
   including judge reads of held-out outputs.
4. **Judging** follows the dev-set protocol (`../seeded_defects/JUDGING.md`)
   unchanged: same HIT criteria, same scoring, frontier judge.
5. **Results are published either way** (REPORT.md), including dev→held-out
   score drops. A drop is a finding, not a failure to hide.

## Contents

- Two projects in domains disjoint from the dev set (fintech-SaaS, logistics-SaaS):
  - **prepnest** — consumer edtech, minor-age users (safeguarding-critical)
  - **kilnshare** — two-sided P2P equipment-rental marketplace (liability-critical)
- 8 docs per project: 5 spec + 3 research (the research trio + clean PRD/GTM
  also serve as fixed inputs for held-out GENERATOR validation, mirroring
  `gen_runner.py`'s dev-set design)
- `manifest.yaml`: 15 defects mirroring the dev set's type × severity ×
  expected-agent distribution exactly (8 obvious / 7 subtle), all fresh
  manifestations.

## Authorship note

Authored 2026-08-06 by the same author as the dev set (Claude, frontier),
consistent-by-construction numbers, before any candidate configuration was
run against it. The contamination this set guards against is *iterative
tuning*, which no amount of authorship care prevents on the dev set — not
authorship bias, which is shared with the dev set by design (scores stay
comparable).

## Exposure log

| Date | Role family | Configuration | Purpose | Result recorded in |
|---|---|---|---|---|
| 2026-08-08 | Adversarial review (decomposed DA, 6 passes) | Frozen at commit e041e5e: five narrow passes on qwen3:8b, open-critique gen+judge on qwen3.6:35b (repeats=2); composed via run_decomposed_da | Phase 3 verdict — single shot, dev band ~11-13/15 & 0-2 clean FP | evals/REPORT.md (Phase 3 section) |
