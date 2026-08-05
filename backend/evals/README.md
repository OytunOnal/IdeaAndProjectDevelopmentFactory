# evals/

Evaluation assets for the agent pipeline. See the root `EVAL_PLAN.md` for the full design.

## Layout

- `fixtures/golden_intents.yaml` — discussion-layer intent classification golden set
  (~50 cases, 17 categories: approvals, revisions, rewrites, reopens, improves,
  questions, ambiguity, multi-intent, politeness, typos, code-switching, emotion,
  off-topic/injection, wrong-target traps, conditionals, negations, completed-phase).
  Cases tagged `regression` are distilled from real past bugs.
- `results/` — eval run outputs (JSON, with run metadata: models per role, rubric
  version, git sha, date). Git-ignored except summaries.

## Status

- [x] Golden-intent fixtures (68 cases) + `eval_runner.py` — real code path, 9 runs across 6 configs
- [x] Seeded-defect fixtures (15 defects, 2 projects) + `defect_runner.py` + human-judge protocol
- [x] **`REPORT.md` — role × model matrix v1 and decisions** · full judge detail in `JUDGE_SCORES.md`
- [ ] Next: DA prompt upgrade (absence-scan + evidence-verify) → re-measure; intent hardening → re-measure; spec-writer + judge meta-evals (`EVAL_PLAN.md` steps 2/4)

## Principles (short form)

Deterministic asserts first; judge only where code can't decide; judge must pass
consistency/sensitivity/calibration before its scores count; blind pairwise with
position swap for comparisons; small honest sets over big noisy ones.
