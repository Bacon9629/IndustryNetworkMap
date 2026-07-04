"""Load extracted candidate relationships into Neo4j.

Usage (from ingestion/):
    python rag/load_candidates.py [--candidates rag/extracted/candidates.jsonl]

鐵律：一律寫入 status=candidate、created_by=llm_extraction、value_type=inferred。
既有同 id 關係以 MERGE 更新（同一 chunk 重跑不重複）。審核走 /review UI。
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase


def candidate_id(rec: dict) -> str:
    key = f"{rec['from_id']}|{rec['type']}|{rec['to_id']}|{rec['chunk_id']}"
    return "llm_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(Path(__file__).parent / "extracted" / "candidates.jsonl"))
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "industrymap_dev"))
    args = parser.parse_args()

    records = [json.loads(line) for line in Path(args.candidates).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise SystemExit("candidates.jsonl 為空，請先執行 extract.py")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    n = 0
    try:
        with driver.session() as session:
            for rec in records:
                props = {
                    "confidence": rec["confidence"],
                    "status": "candidate",
                    "created_by": "llm_extraction",
                    "value_type": "inferred",
                    "evidence": rec["evidence"],
                    "source_ids": [rec["source_id"]],
                    "chunk_id": rec["chunk_id"],
                }
                if rec.get("period"):
                    props["period"] = rec["period"]
                if rec.get("product_id"):
                    props["product_id"] = rec["product_id"]
                # from/to label 與 type 已在 extract.py 依 REL_TYPE_RULES 驗證
                session.run(
                    f"MATCH (a:{rec['from_label']} {{id: $from_id}}), (b:{rec['to_label']} {{id: $to_id}}) "
                    f"MERGE (a)-[r:{rec['type']} {{id: $rel_id}}]->(b) "
                    "ON CREATE SET r.created_at = $now "
                    "SET r += $props, r.updated_at = $now",
                    from_id=rec["from_id"], to_id=rec["to_id"],
                    rel_id=candidate_id(rec), props=props, now=now,
                )
                n += 1
        print(f"已寫入 {n} 條 candidate 關係（status=candidate, created_by=llm_extraction）。請至 /review 審核。")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
