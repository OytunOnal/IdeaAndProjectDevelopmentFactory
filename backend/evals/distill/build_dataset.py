"""Phase 4 step 3 — compile labeled candidates into a training dataset.

Each labeled candidate becomes one SFT example for the judge task:
- user turn: the PRODUCTION judge prompt (_CRITIQUE_VERIFY_PROMPT), formatted
  exactly as the runtime formats it — so the trained adapter drops into
  production with zero prompt changes.
- assistant turn: a JSON object with the rationale FIRST and the verdict
  second ({"rationale": ..., "genuine": ...}) — rationale-first lets the
  autoregressive student reason before committing, and the production parser
  (_parse_verdict_key) reads "genuine" regardless of extra keys.

Split discipline: BY PROJECT, never by row. An eval project contributes
nothing to training. The picker targets an eval slice holding ~15-25% of all
genuine labels so both classes are testable.

Usage (from backend/):
    python -m evals.distill.build_dataset            # writes data/dataset/
    python -m evals.distill.build_dataset --eval-projects courtly,floatplan,stagehand,vetvisit
"""

import argparse
import collections
import json
import random
import re
from pathlib import Path

from app.agents.decomposed_da import _CRITIQUE_VERIFY_PROMPT

DATA = Path(__file__).parent / "data"
OUT = DATA / "dataset"


def _sanitize_rationale(row: dict) -> str:
    """Code-label rationales reference the corpus construction ("planted",
    "auto") — the student must never learn that vocabulary. Rebuild them
    from the candidate's own issue text."""
    if row["label_source"] == "code" and row.get("rationale_source") != "teacher-opus":
        issue = re.split(r"(?<=[.!?])\s", row["issue"].strip())[0]
        issue = re.sub(r"(?i)planted\s+", "", issue).rstrip(".")
        return f"The quoted text is a real defect in the document: {issue}."
    return row["rationale"]


def load_rows() -> list[dict]:
    rows = []
    for f in sorted((DATA / "labels").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
    return rows


def doc_text_for(row: dict) -> str:
    variant = row["variant"]
    doc_file = f"{variant}.md" if not variant.startswith("clean_") else f"{variant.removeprefix('clean_')}.md"
    return (DATA / "projects" / row["project"] / doc_file).read_text(encoding="utf-8")


def to_example(row: dict) -> dict:
    prompt = _CRITIQUE_VERIFY_PROMPT.format(
        doc_key=row["doc"], doc_text=doc_text_for(row),
        category=row["category"], issue=row["issue"], quote=row["quote"],
    )
    completion = json.dumps(
        {"rationale": _sanitize_rationale(row), "genuine": row["genuine"]},
        ensure_ascii=False,
    )
    return {"messages": [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": f"```json\n{completion}\n```"},
    ]}


def pick_eval_projects(rows: list[dict], k: int = 4, seed: int = 17) -> list[str]:
    """Seeded search for an eval slice holding 15-25% of all genuines."""
    by_project: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_project[r["project"]].append(r)
    projects = sorted(by_project)
    total_gen = sum(r["genuine"] for r in rows)
    rng = random.Random(seed)
    for _ in range(500):
        cand = rng.sample(projects, k)
        gen = sum(r["genuine"] for p in cand for r in by_project[p])
        if 0.15 <= gen / max(total_gen, 1) <= 0.25:
            return sorted(cand)
    return sorted(projects[:k])  # deterministic fallback


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-projects", default=None,
                    help="comma-separated project names; default: seeded stratified pick")
    args = ap.parse_args()

    rows = load_rows()
    eval_projects = (args.eval_projects.split(",") if args.eval_projects
                     else pick_eval_projects(rows))
    OUT.mkdir(parents=True, exist_ok=True)

    splits = {"train": [], "eval": []}
    for r in rows:
        splits["eval" if r["project"] in eval_projects else "train"].append(r)

    stats: dict = {"eval_projects": eval_projects}
    for name, subset in splits.items():
        rng = random.Random(41)
        rng.shuffle(subset)
        path = OUT / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for r in subset:
                f.write(json.dumps(to_example(r), ensure_ascii=False) + "\n")
        stats[name] = {
            "rows": len(subset),
            "genuine": sum(r["genuine"] for r in subset),
            "by_category": dict(collections.Counter(r["category"] for r in subset)),
            "by_label_source": dict(collections.Counter(r["label_source"] for r in subset)),
        }
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
