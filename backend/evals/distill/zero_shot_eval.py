"""Stage A — zero-shot base-candidate shootout on the sealed judge eval.

Feeds the 174 eval.jsonl prompts (production judge prompt, verbatim) to an
Ollama model with no training, and scores per-category P/R with the same
parse as the Colab notebook. Anchor: base Qwen3-8B on Colab = P0.24/R0.67.

Usage (from backend/):
    python -m evals.distill.zero_shot_eval --model hermes3:8b
    python -m evals.distill.zero_shot_eval --model qwen3:8b --limit 20
"""

import argparse
import collections
import json
import re
import time
from pathlib import Path

import requests

DATASET = Path(__file__).parent / "data" / "dataset" / "eval.jsonl"
OUT = Path(__file__).parent / "data" / "zero_shot"
OLLAMA = "http://localhost:11434/api/chat"


def judge(model: str, user_content: str, num_predict: int) -> str:
    r = requests.post(OLLAMA, json={
        "model": model,
        "messages": [{"role": "user", "content": user_content}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": num_predict, "num_ctx": 8192},
    }, timeout=900)
    r.raise_for_status()
    return r.json()["message"]["content"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--num-predict", type=int, default=220,
                    help="generation cap; non-default runs get their own log file")
    args = ap.parse_args()

    rows = [json.loads(l) for l in DATASET.read_text(encoding="utf-8").splitlines()]
    if args.limit:
        rows = rows[: args.limit]

    OUT.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.model.lower())
    if args.num_predict != 220:
        slug += f"-np{args.num_predict}"
    log_path = OUT / f"{slug}.jsonl"
    done = set()
    if log_path.exists():  # resume
        for l in log_path.read_text(encoding="utf-8").splitlines():
            done.add(json.loads(l)["i"])

    stats: dict = collections.defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "unparsed": 0})
    t0 = time.time()
    with log_path.open("a", encoding="utf-8") as log:
        for i, row in enumerate(rows):
            user = row["messages"][0]["content"]
            gold = json.loads(re.sub(r"^```json\n|\n```$", "", row["messages"][1]["content"]))["genuine"]
            if i in done:
                continue
            reply = judge(args.model, user, args.num_predict)
            m = re.search(r'"genuine"\s*:\s*(true|false)', reply)
            pred = (m.group(1) == "true") if m else None
            log.write(json.dumps({"i": i, "gold": gold, "pred": pred, "reply": reply[:400]},
                                 ensure_ascii=False) + "\n")
            log.flush()
            if (len(done) + i + 1) % 20 == 0:
                el = time.time() - t0
                print(f"{i + 1}/{len(rows)}  ({el / 60:.1f} dk)")

    # score from the full log (includes resumed rows)
    replies = {json.loads(l)["i"]: json.loads(l)
               for l in log_path.read_text(encoding="utf-8").splitlines()}
    for i, row in enumerate(rows):
        if i not in replies:
            continue
        rec = replies[i]
        cat_m = re.search(r"Proposed finding \(([^)]+)\)", row["messages"][0]["content"])
        cat = cat_m.group(1) if cat_m else "?"
        for key in (cat, "TOTAL"):
            s = stats[key]
            if rec["pred"] is None:
                s["unparsed"] += 1
            elif rec["pred"] and rec["gold"]:
                s["tp"] += 1
            elif rec["pred"] and not rec["gold"]:
                s["fp"] += 1
            elif not rec["pred"] and rec["gold"]:
                s["fn"] += 1
            else:
                s["tn"] += 1

    print(f"\nmodel: {args.model}")
    print(f"{'category':28s} {'P':>6s} {'R':>6s} {'n':>5s} {'unparsed':>9s}")
    for cat, s in sorted(stats.items()):
        n = s["tp"] + s["fp"] + s["fn"] + s["tn"] + s["unparsed"]
        p = s["tp"] / max(s["tp"] + s["fp"], 1)
        r = s["tp"] / max(s["tp"] + s["fn"], 1)
        print(f"{cat:28s} {p:6.2f} {r:6.2f} {n:5d} {s['unparsed']:9d}")


if __name__ == "__main__":
    main()
