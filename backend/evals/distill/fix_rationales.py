"""Phase 4 fix — replace templated code-label rationales with teacher-written ones.

Measured failure: the first trained adapter collapsed to a yes-sayer (P 0.22 /
R 0.97 on eval). Cause: all 95 code-labeled genuine examples shared ONE
sanitized rationale template while the 500+ negatives carried varied teacher
prose — rationale STYLE became a proxy for the label, and with rationale-first
completions the memorized opening locks the verdict to true.

Cure: have the teacher write the genuine rationales too, so style is
independent of label.

Usage (from backend/):
    python -m evals.distill.fix_rationales export   # writes data/rationale_queue/PROMPT.md
    python -m evals.distill.fix_rationales import --file <teacher-reply.jsonl>
"""

import argparse
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
LABELS = DATA / "labels"
QUEUE = DATA / "rationale_queue"

_PROMPT_HEADER = """You are reviewing findings that a document auditor raised against product \
spec documents. Each finding below has already been verified as a genuine defect. \
Your task is ONLY to write the justification.

For each numbered item, write a rationale of 1-2 sentences (max 300 characters) \
explaining WHY the quoted text is a real defect of the stated category — \
grounded in the issue and quote, in your own words. Vary your sentence \
structure across items; do not reuse one opening phrase.

Return ONLY a JSONL code block, one line per item:
{"key": "<key copied verbatim>", "rationale": "<your 1-2 sentences>"}

Items:
"""


def _code_genuine_rows() -> list[dict]:
    rows = []
    for f in sorted(LABELS.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["label_source"] == "code" and r["genuine"]:
                rows.append(r)
    return rows


def export() -> None:
    rows = _code_genuine_rows()
    QUEUE.mkdir(parents=True, exist_ok=True)
    parts = [_PROMPT_HEADER]
    for i, r in enumerate(rows, 1):
        parts.append(
            f"{i}. key: {r['key']}\n"
            f"   category: {r['category']}\n"
            f"   issue: {r['issue']}\n"
            f"   quote: {r['quote']}\n"
        )
    (QUEUE / "PROMPT.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"{len(rows)} items -> {QUEUE / 'PROMPT.md'}")


def import_(path: str) -> None:
    replies = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        r = json.loads(line)
        replies[r["key"]] = r["rationale"][:300]

    updated = 0
    for f in sorted(LABELS.glob("*.jsonl")):
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
        changed = False
        for r in rows:
            if r["key"] in replies:
                r["rationale"] = replies.pop(r["key"])
                r["rationale_source"] = "teacher-opus"
                changed = True
                updated += 1
        if changed:
            f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                         encoding="utf-8")
    print(f"updated {updated} rows; unmatched replies: {sorted(replies)}")

    expected = [r["key"] for r in _code_genuine_rows()
                if r.get("rationale_source") != "teacher-opus"]
    print(f"code-genuine rows still templated: {len(expected)}")
    for k in expected[:10]:
        print("  missing:", k)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["export", "import"])
    ap.add_argument("--file", help="teacher reply jsonl (import stage)")
    args = ap.parse_args()
    if args.stage == "export":
        export()
    else:
        assert args.file, "--file required"
        import_(args.file)


if __name__ == "__main__":
    main()
