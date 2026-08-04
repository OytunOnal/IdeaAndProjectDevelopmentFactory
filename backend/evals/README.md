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

- [x] Step 0: golden intent fixtures
- [ ] Step 0: `eval_runner.py` — wire fixtures to the discussion-intent classifier
      (call the same code path `research_discussion` / `review_discussion` use,
      with a mocked state built from each case's `context`)
- [ ] Step 1+: see `EVAL_PLAN.md`

## Principles (short form)

Deterministic asserts first; judge only where code can't decide; judge must pass
consistency/sensitivity/calibration before its scores count; blind pairwise with
position swap for comparisons; small honest sets over big noisy ones.
