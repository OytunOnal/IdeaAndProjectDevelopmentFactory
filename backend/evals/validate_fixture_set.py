"""Mechanically verify an externally authored fixture set.

Sets written by a different model family (see fixtures/AUTHORING_BRIEF.md)
arrive unverified: patches drift, documents go missing, distributions skew.
This checks what code can check and reports what a human should spot-check.

Deliberately withholding: the report prints names, counts, types and
integrity results — never document or defect TEXT. The system's author
reading fixture content is the contamination this whole arrangement exists
to prevent; a validator that dumps the set defeats it.

Usage (from backend/):
    python -m evals.validate_fixture_set --dir evals/fixtures/heldout3
"""

import argparse
import collections
from pathlib import Path

import yaml

SPEC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")

# Classes earlier sets already used — anything else counts as novel coverage,
# which is the point of commissioning an external set.
KNOWN_TYPES = {
    "internal-contradiction", "arithmetic-error", "impossible-math",
    "fabricated-evidence", "cross-doc-inconsistency", "missing-critical",
    "out-of-scope-reference", "absurd-target", "audience-mismatch",
    "infeasible-plan", "infeasible-tech",
}


def check(root: Path) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    manifest_path = root / "manifest.yaml"
    if not manifest_path.exists():
        print(f"FAIL: no manifest.yaml in {root}")
        return 1
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"FAIL: manifest.yaml does not parse: {e}")
        return 1
    if not isinstance(manifest, list) or not manifest:
        print("FAIL: manifest.yaml is not a non-empty list")
        return 1

    projects = sorted({d.get("project") for d in manifest if isinstance(d, dict)})
    print(f"set: {root}")
    print(f"projects: {projects}")

    # documents present and non-trivial
    for project in projects:
        pdir = root / str(project)
        if not pdir.is_dir():
            errors.append(f"missing project directory: {project}")
            continue
        for key in SPEC_KEYS:
            f = pdir / f"{key}.md"
            if not f.exists():
                errors.append(f"{project}: missing {key}.md")
            elif len(f.read_text(encoding="utf-8").split()) < 80:
                warnings.append(f"{project}/{key}.md is very short (<80 words)")

    # manifest field integrity + patch application
    ids: set[str] = set()
    types: collections.Counter = collections.Counter()
    severities: collections.Counter = collections.Counter()
    per_project: collections.Counter = collections.Counter()
    for i, d in enumerate(manifest):
        where = d.get("id", f"entry#{i}")
        for field in ("id", "project", "doc", "type", "severity", "patch", "detection"):
            if field not in d:
                errors.append(f"{where}: missing field '{field}'")
        if d.get("id") in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(d.get("id"))
        if d.get("doc") not in SPEC_KEYS:
            errors.append(f"{where}: doc '{d.get('doc')}' is not a spec document")
        if d.get("severity") not in ("obvious", "subtle"):
            warnings.append(f"{where}: severity '{d.get('severity')}' is not obvious|subtle")
        types[d.get("type")] += 1
        severities[d.get("severity")] += 1
        per_project[d.get("project")] += 1

        patch = d.get("patch") or {}
        find = patch.get("find")
        if not isinstance(find, str) or not find:
            errors.append(f"{where}: patch.find missing or empty")
            continue
        if "replace" not in patch:
            errors.append(f"{where}: patch.replace missing (use \"\" to delete)")
        doc_path = root / str(d.get("project")) / f"{d.get('doc')}.md"
        if not doc_path.exists():
            continue  # already reported
        text = doc_path.read_text(encoding="utf-8")
        count = text.count(find)
        if count != 1:
            errors.append(f"{where}: patch.find matches {count}x in {d.get('doc')}.md (must be exactly 1)")

    # traps (optional but expected from the brief)
    traps_path = root / "traps.yaml"
    n_traps = 0
    if traps_path.exists():
        try:
            traps = yaml.safe_load(traps_path.read_text(encoding="utf-8")) or []
            n_traps = len(traps)
            for t in traps:
                if "why_defensible" not in t:
                    warnings.append(f"trap {t.get('id', '?')}: missing why_defensible")
        except yaml.YAMLError as e:
            errors.append(f"traps.yaml does not parse: {e}")
    else:
        warnings.append("no traps.yaml — precision control passages are missing")

    novel = {t for t in types if t not in KNOWN_TYPES}
    novel_count = sum(types[t] for t in novel)

    print(f"defects: {len(manifest)} | per project: {dict(per_project)}")
    print(f"severity: {dict(severities)}")
    print(f"types: {dict(types.most_common())}")
    print(f"novel classes: {sorted(novel) or 'none'} ({novel_count} defects)")
    print(f"traps: {n_traps}")

    if novel_count < 6:
        warnings.append(f"only {novel_count} defects in novel classes (brief asks for >=6)")
    if n_traps and n_traps < 3:
        warnings.append(f"only {n_traps} traps (brief asks for 3)")

    print()
    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"FAIL: {e}")
    if not errors:
        print("\nStructural checks passed. Still needs a human spot-check: are the"
              "\nclean documents' numbers actually self-consistent, and does each"
              "\n'detection' line describe a defect a competent reviewer would flag?")
    return 1 if errors else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="fixture set directory (contains manifest.yaml)")
    args = ap.parse_args()
    raise SystemExit(check(Path(args.dir)))


if __name__ == "__main__":
    main()
