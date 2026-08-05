# Local-vs-Frontier Agent Evaluation — Report v1 (2026-08-05)

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
