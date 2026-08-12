"""Phase 4 step 2 — candidate generation + labeling for the judge task.

The #1 distillation target is the critique-judge: "is this candidate
finding genuine?" — the evaluative judgment the fast model failed in every
prompt framing (Phase 3). Training rows are (document, candidate, verdict).

Candidates come from the REAL distribution: the production critique
extractor (fast model, same prompt/temperature) run over the synthetic
corpus — clean and defected variants alike.

Labels come from three sources (decided 2026-08-10):
1. CODE (free, certain): on a defected doc, a candidate whose quote
   overlaps the planted quote is genuine=true by construction; the planted
   quote itself is also emitted as a guaranteed-positive candidate.
2. TEACHER = Claude Opus via chat sessions (subscription, not API): the
   `export` stage writes self-contained queue files; an Opus session
   labels them; `import` merges the labels back. Rationales are kept for
   rationale-distillation.
3. META-EVAL: a random sample of teacher labels is independently re-judged
   by the session judge (Fable) before the teacher's labels are trusted —
   the same bar the migration plan sets for any judge role.

Usage (from backend/):
  # 1. candidates (local fast model; run AFTER corpus generation — same GPU):
  LLM_FORCE_PROVIDER=ollama OLLAMA_MODEL_FAST=qwen3:8b OLLAMA_MODEL_QUALITY=qwen3:8b \
      python -m evals.distill.label_candidates --stage candidates
  # 2. auto-labels + teacher queue files:
  python -m evals.distill.label_candidates --stage export
  # 3. (an Opus chat session processes data/teacher_queue/*.json → *.labels.jsonl)
  # 4. merge teacher labels:
  python -m evals.distill.label_candidates --stage import
  python -m evals.distill.label_candidates --stage stats
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from app.agents.decomposed_da import (
    _CRITIQUE_PROMPT,
    CRITIQUE_CATEGORIES,
    _normalize_ws,
    _parse_items,
)
from app.agents.llm import call_llm

DATA = Path(__file__).parent / "data"
SPEC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")

# Map planted defect types to the critique category vocabulary (the judge
# task's label space). Types owned by other passes still yield candidates —
# the judge must recognize e.g. a planted arithmetic error as genuine when
# the critique extractor happens to surface it.
TYPE_TO_CATEGORY = {
    "internal-contradiction": "internal-contradiction",
    "infeasible-tech": "infeasible-tech",
    "absurd-target": "absurd-target",
    "audience-mismatch": "audience-mismatch",
    "infeasible-plan": "infeasible-plan",
    "arithmetic-error": "internal-contradiction",
    "fabricated-evidence": "internal-contradiction",
}

TEACHER_INSTRUCTION = (
    "You are the reference judge producing training labels for a smaller "
    "model. Each candidate below is a proposed review finding against one of "
    "the documents in this file; the candidate's 'variant' field names the "
    "document it belongs to. Judge EACH candidate with two duties of EQUAL "
    "weight: genuine, serious flaws MUST be labeled true; manufactured "
    "criticism (defensible choices, stylistic nitpicks, misreadings) MUST "
    "be labeled false. The bar: would a competent reviewer stake their "
    "name on this finding as stated? Output: a JSONL file next to this one "
    "named <this-file-stem>.labels.jsonl, one line per candidate, no other "
    "commentary: "
    '{"key": "<key>", "genuine": true/false, "rationale": "<one sentence>"}'
)


def _iter_projects() -> list[Path]:
    root = DATA / "projects"
    return sorted(p for p in root.iterdir() if (p / "defects.json").exists()) if root.exists() else []


# ── stage: candidates (local fast model) ───────────────────────────────────

async def stage_candidates(samples: int = 3) -> None:
    """Run the production critique extractor over every doc variant."""
    outdir = DATA / "candidates"
    outdir.mkdir(parents=True, exist_ok=True)
    for project in _iter_projects():
        out = outdir / f"{project.name}.jsonl"
        if out.exists():
            print(f"  [{project.name}] exists — skipped")
            continue
        defects = json.loads((project / "defects.json").read_text(encoding="utf-8"))
        variants: list[tuple[str, str, str, dict | None]] = []
        for key in SPEC_KEYS:
            variants.append((f"clean_{key}", key, (project / f"{key}.md").read_text(encoding="utf-8"), None))
        for d in defects:
            variants.append((d["file"].removesuffix(".md"), d["doc"],
                            (project / d["file"]).read_text(encoding="utf-8"), d))

        rows: list[dict] = []
        t0 = time.perf_counter()
        for variant_id, doc_key, doc_text, defect in variants:
            seen: set[str] = set()
            for _ in range(samples):
                try:
                    reply = await call_llm(
                        messages=[
                            {"role": "system", "content": _CRITIQUE_PROMPT},
                            {"role": "user", "content": f"Document ({doc_key}):\n\n{doc_text}"},
                        ],
                        model_tier=2, temperature=0.7, max_tokens=1536,
                        role="audit", think=False,
                    )
                except Exception as e:
                    print(f"    extraction failed ({variant_id}): {e}")
                    continue
                for item in _parse_items(reply):
                    quote, issue = item.get("quote", ""), item.get("issue", "")
                    category = item.get("category", "")
                    if not quote or not issue or category not in CRITIQUE_CATEGORIES:
                        continue
                    if _normalize_ws(quote) not in _normalize_ws(doc_text):
                        continue
                    key = _normalize_ws(quote).lower()
                    if any(key in s or s in key for s in seen):
                        continue
                    seen.add(key)
                    rows.append({
                        "project": project.name, "variant": variant_id, "doc": doc_key,
                        "quote": quote, "issue": issue, "category": category,
                        "planted_type": defect["type"] if defect else None,
                        "planted_quote": defect["planted_quote"] if defect else None,
                    })
            # guaranteed positive: the planted quote itself as a candidate
            if defect is not None:
                key = _normalize_ws(defect["planted_quote"]).lower()
                if not any(key in s or s in key for s in seen):
                    rows.append({
                        "project": project.name, "variant": variant_id, "doc": doc_key,
                        "quote": defect["planted_quote"],
                        "issue": defect.get("note") or f"Planted {defect['type']} defect.",
                        "category": TYPE_TO_CATEGORY.get(defect["type"], "internal-contradiction"),
                        "planted_type": defect["type"], "planted_quote": defect["planted_quote"],
                        "synthetic_positive": True,
                    })
        with out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"  [{project.name}] {len(rows)} candidates in {time.perf_counter() - t0:.0f}s")


# ── stage: export (auto-labels + teacher queue) ────────────────────────────

def _auto_label(row: dict) -> bool | None:
    """Code-derived label where construction makes it certain."""
    if row.get("synthetic_positive"):
        return True
    planted = row.get("planted_quote")
    if planted:
        q, p = _normalize_ws(row["quote"]).lower(), _normalize_ws(planted).lower()
        if q in p or p in q:
            return True  # candidate found the planted defect
    return None  # everything else goes to the teacher


def _row_key(row: dict, index: int) -> str:
    return f"{row['project']}/{row['variant']}#{index}"


def stage_export() -> None:
    """Write code labels directly; queue everything else for the Opus teacher."""
    labels_dir = DATA / "labels"
    queue_dir = DATA / "teacher_queue"
    labels_dir.mkdir(parents=True, exist_ok=True)
    queue_dir.mkdir(parents=True, exist_ok=True)

    for cand_file in sorted((DATA / "candidates").glob("*.jsonl")):
        project = cand_file.stem
        out = labels_dir / f"{project}.jsonl"
        done: set[str] = set()
        if out.exists():
            for line in out.read_text(encoding="utf-8").splitlines():
                done.add(json.loads(line)["key"])
        rows = [json.loads(line) for line in cand_file.read_text(encoding="utf-8").splitlines()]

        auto_n = 0
        pending: dict[str, list[dict]] = {}  # variant -> rows
        with out.open("a", encoding="utf-8") as f:
            for i, row in enumerate(rows):
                key = _row_key(row, i)
                if key in done:
                    continue
                auto = _auto_label(row)
                if auto is not None:
                    f.write(json.dumps({"key": key, **row, "genuine": auto,
                                        "rationale": "auto: planted-defect construction",
                                        "label_source": "code"}, ensure_ascii=False) + "\n")
                    auto_n += 1
                else:
                    pending.setdefault(row["variant"], []).append({"key": key, **row})

        # One queue file per PROJECT, not per variant. Each file is processed
        # in a single teacher session, so per-variant files (20 projects x ~10
        # variants = ~200 sessions) would be unusable by hand; per-project is
        # ~20 sessions of ~35 candidates each, which one response can cover.
        if not pending:
            print(f"  [{project}] auto-labeled {auto_n}, nothing left for the teacher")
            continue
        documents: dict[str, str] = {}
        candidates: list[dict] = []
        for variant, vrows in sorted(pending.items()):
            doc_file = f"{variant}.md" if not variant.startswith("clean_") else f"{variant.removeprefix('clean_')}.md"
            documents[variant] = (DATA / "projects" / project / doc_file).read_text(encoding="utf-8")
            candidates.extend({"key": r["key"], "variant": variant, "doc": r["doc"],
                               "category": r["category"], "issue": r["issue"],
                               "quote": r["quote"]} for r in vrows)
        qfile = queue_dir / f"{project}.json"
        qfile.write_text(json.dumps({
            "instruction": TEACHER_INSTRUCTION,
            "project": project,
            "documents": documents,
            "candidates": candidates,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [{project}] auto-labeled {auto_n}, queued {len(candidates)} "
              f"across {len(documents)} document(s) -> {qfile.name}")


# ── stage: import (merge teacher labels) ───────────────────────────────────

def stage_import() -> None:
    """Merge *.labels.jsonl files the teacher session produced."""
    labels_dir = DATA / "labels"
    queue_dir = DATA / "teacher_queue"
    # index all candidates by key
    by_key: dict[str, dict] = {}
    for cand_file in sorted((DATA / "candidates").glob("*.jsonl")):
        rows = [json.loads(line) for line in cand_file.read_text(encoding="utf-8").splitlines()]
        for i, row in enumerate(rows):
            by_key[_row_key(row, i)] = row

    merged = skipped = 0
    for lfile in sorted(queue_dir.glob("*.labels.jsonl")):
        for line in lfile.read_text(encoding="utf-8").splitlines():
            try:
                label = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            key, genuine = label.get("key"), label.get("genuine")
            row = by_key.get(key)
            if row is None or not isinstance(genuine, bool):
                skipped += 1
                continue
            out = labels_dir / f"{row['project']}.jsonl"
            done = set()
            if out.exists():
                done = {json.loads(x)["key"] for x in out.read_text(encoding="utf-8").splitlines()}
            if key in done:
                continue
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, **row, "genuine": genuine,
                                    "rationale": str(label.get("rationale", ""))[:300],
                                    "label_source": "teacher-opus"}, ensure_ascii=False) + "\n")
            merged += 1
    print(f"merged {merged} teacher labels ({skipped} skipped/unmatched)")


def _stats() -> None:
    labels = sorted((DATA / "labels").glob("*.jsonl")) if (DATA / "labels").exists() else []
    total = pos = teacher = 0
    for f in labels:
        for line in f.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            total += 1
            pos += row["genuine"]
            teacher += row["label_source"].startswith("teacher")
    cands = sorted((DATA / "candidates").glob("*.jsonl")) if (DATA / "candidates").exists() else []
    n_cands = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in cands)
    queue = sorted((DATA / "teacher_queue").glob("*.json")) if (DATA / "teacher_queue").exists() else []
    print(f"candidates: {n_cands} across {len(cands)} project(s)")
    print(f"labels: {total} ({pos} genuine / {total - pos} not; {teacher} teacher-labeled)")
    print(f"teacher queue files: {len(queue)}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["candidates", "export", "import", "stats"], required=True)
    args = ap.parse_args()
    if args.stage == "candidates":
        await stage_candidates()
    elif args.stage == "export":
        stage_export()
    elif args.stage == "import":
        stage_import()
    else:
        _stats()


if __name__ == "__main__":
    asyncio.run(main())
