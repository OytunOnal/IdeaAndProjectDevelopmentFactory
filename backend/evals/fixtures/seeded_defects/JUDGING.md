# Seeded-Defect Eval — Judging Protocol

Judge: Claude (in-session), following this written protocol so scoring is
consistent across models and runs. The judge reads each generated report
against `manifest.yaml` and scores **before** seeing other models' reports
for the same bundle (no cross-model anchoring within a scoring pass).

## Recall scoring (defected bundles)

Per defect, against its `detection` criterion:

- **HIT (1.0)** — the report substantively identifies the planted issue:
  right document/claim, right problem. Paraphrase counts; quoting the
  planted text is not required; proposing a fix implies identification.
- **PARTIAL (0.5)** — the report touches the right area but misses the
  core (e.g. questions the pricing section generally but never notices the
  $19-vs-$12 conflict; complains the timeline is "tight" without flagging
  it as infeasible).
- **MISS (0.0)** — not identified, or mentioned so vaguely that a reader
  wouldn't learn anything is wrong there.

Recall = mean score over the bundle's defects, reported overall and split
by severity (obvious/subtle) and by type.

## False-positive scoring (clean bundles)

The DA's *job* is to criticize — raising risks on a clean bundle is NOT a
false positive. An FP is counted only when the report **misstates the
documents**:

- **FABRICATION** — asserts the docs say something they don't ("the PRD
  promises unlimited invoices" when it doesn't), or invents numbers/claims
  and attributes them to the docs.
- **FALSE CONFLICT** — claims two documents contradict each other when the
  quoted/referenced passages are actually consistent.

Judgment calls, opinions, severity inflation, and generic risk-raising are
recorded qualitatively but not counted as FPs. FP rate = count per report.

## Report-quality notes (qualitative, not scored)

For each report the judge also notes: mitigation quality (the pipeline
requires every problem to carry a fix), structure compliance (Recommended
Adjustments section present and honest), and hallucination smell.

## Fairness rules

- Same bundles, same prompts, same truncation (docs_context 2500 chars/doc)
  for every model.
- Judge scores from the manifest criteria, not from memory of what other
  models found.
- Ambiguous cases resolve DOWNWARD (PARTIAL not HIT, no-FP not FP) and are
  flagged in the notes for transparency.
