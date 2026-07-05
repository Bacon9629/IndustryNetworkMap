"""Select high-value chunks for LLM relationship extraction.

This creates a small JSONL queue from chunks.jsonl so extraction can progress
company by company without blindly sending every filing chunk to the LLM.

Usage:
    python rag/select_extraction_chunks.py --company-id US_NVDA --limit 30
    python rag/select_extraction_chunks.py --universe US_LARGE_CAP_RESEARCH_UNIVERSE --limit-per-company 8
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


KEYWORDS = [
    "supplier",
    "suppliers",
    "supply",
    "customer",
    "customers",
    "client",
    "clients",
    "contract manufacturer",
    "manufacturing partner",
    "distributor",
    "reseller",
    "competition",
    "competitor",
    "compete",
    "revenue by",
    "segment",
    "products include",
    "services include",
    "data center",
    "AI",
    "semiconductor",
    "cloud",
]


def read_progress(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def score(text: str, company_terms: list[str]) -> int:
    lower = text.lower()
    total = 0
    for keyword in KEYWORDS:
        if keyword.lower() in lower:
            total += 2
    for term in company_terms:
        term = term.strip().lower()
        if term and term in lower:
            total += 1
    return total


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    parser.add_argument("--progress", default=str(Path(__file__).resolve().parents[1] / "progress" / "company_update_progress.csv"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "extracted" / "selected_chunks.jsonl"))
    parser.add_argument("--company-id", help="Select chunks for one company.")
    parser.add_argument("--universe", help="Select companies from company_update_progress.csv by universe_type.")
    parser.add_argument("--limit", type=int, default=30, help="Limit for --company-id.")
    parser.add_argument("--limit-per-company", type=int, default=8, help="Per-company limit for --universe.")
    parser.add_argument("--min-score", type=int, default=2)
    args = parser.parse_args()

    progress_rows = read_progress(Path(args.progress))
    company_terms_by_id: dict[str, list[str]] = {}
    selected_company_ids: set[str] = set()

    if args.company_id:
        selected_company_ids.add(args.company_id)
    if args.universe:
        selected_company_ids.update(
            row["company_id"] for row in progress_rows if row.get("universe_type") == args.universe
        )

    for row in progress_rows:
        company_id = row.get("company_id", "")
        if company_id not in selected_company_ids:
            continue
        company_terms_by_id[company_id] = [row.get("name", ""), row.get("ticker", "")]

    if not selected_company_ids:
        raise SystemExit("Select --company-id or --universe.")

    candidates: dict[str, list[tuple[int, dict]]] = {company_id: [] for company_id in selected_company_ids}
    with Path(args.chunks).open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            company_id = rec.get("company_id")
            if company_id not in selected_company_ids:
                continue
            current_score = score(rec.get("text", ""), company_terms_by_id.get(company_id, []))
            if current_score < args.min_score:
                continue
            candidates[company_id].append((current_score, rec))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with out_path.open("w", encoding="utf-8") as out:
        for company_id in sorted(selected_company_ids):
            limit = args.limit if args.company_id else args.limit_per_company
            ranked = sorted(
                candidates.get(company_id, []),
                key=lambda item: (-item[0], item[1].get("source_id", ""), item[1].get("seq", 0)),
            )[:limit]
            for current_score, rec in ranked:
                out.write(json.dumps({**rec, "selection_score": current_score}, ensure_ascii=False) + "\n")
                total += 1
            print(f"{company_id}: selected {len(ranked)} chunks")

    print(f"Wrote {total} selected chunks to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
