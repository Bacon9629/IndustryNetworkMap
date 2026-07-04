"""Register manifest documents as Source nodes in Neo4j (MERGE, repeatable).

Usage (from ingestion/):
    python rag/register_sources.py [--manifest rag/documents/manifest.csv]
Env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
"""

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

VALID_SOURCE_TYPE = {
    "annual_report", "financial_report", "investor_presentation", "company_website",
    "mops", "exchange_data", "news", "research_report", "manual",
}


def load_manifest(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    errors = []
    for i, row in enumerate(rows, start=1):
        for col in ("file", "source_id", "type", "title"):
            if not (row.get(col) or "").strip():
                errors.append(f"manifest row {i}: 必要欄位 '{col}' 為空")
        if (row.get("type") or "").strip() not in VALID_SOURCE_TYPE:
            errors.append(f"manifest row {i}: source type '{row.get('type')}' 不合法")
        if not (path.parent / row["file"]).exists():
            errors.append(f"manifest row {i}: 檔案 '{row['file']}' 不存在")
    if errors:
        raise SystemExit("manifest 驗證失敗：\n" + "\n".join(f"  - {e}" for e in errors))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(Path(__file__).parent / "documents" / "manifest.csv"))
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "industrymap_dev"))
    args = parser.parse_args()

    rows = load_manifest(Path(args.manifest))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        with driver.session() as session:
            for row in rows:
                props = {k: v.strip() for k, v in row.items() if k != "source_id" and (v or "").strip()}
                props["retrieved_at"] = props.get("retrieved_at", now[:10])
                session.run(
                    "MERGE (s:Source {id: $id}) "
                    "ON CREATE SET s.created_at = $now "
                    "SET s += $props, s.updated_at = $now",
                    id=row["source_id"].strip(), props=props, now=now,
                )
        print(f"已登記 {len(rows)} 個 Source 節點（MERGE，重複執行安全）。")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
