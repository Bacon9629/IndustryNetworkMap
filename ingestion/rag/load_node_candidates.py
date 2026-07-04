"""Load extracted node candidates into Neo4j.

Usage (from ingestion/):
    python rag/load_node_candidates.py [--candidates rag/extracted/node_candidates.jsonl]

鐵律（見 docs/development/data-model.md「節點審核欄位」）：
- 一律寫入 status=candidate、created_by=llm_extraction。
- 禁止覆蓋既有非 candidate（null 或 verified）節點：同 id 節點已存在且非 candidate 一律略過。
- 審核走 /review 頁「候選節點」分頁。
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

LABELS = {"Company", "Product", "Industry", "Application"}
LIST_FIELDS = {"aliases", "source_ids", "chunk_ids"}
SKIP_FIELDS = {"label", "chunk_ids"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(Path(__file__).parent / "extracted" / "node_candidates.jsonl"))
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "industrymap_dev"))
    args = parser.parse_args()

    path = Path(args.candidates)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    if not records:
        raise SystemExit(f"{path} 為空或不存在，請先執行 rag/extract_entities.py")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    n_created = n_skipped = 0
    try:
        with driver.session() as session:
            for rec in records:
                label = rec.get("label")
                if label not in LABELS:
                    print(f"跳過：未知 label '{label}'（{rec.get('id')}）")
                    n_skipped += 1
                    continue

                existing = session.run(
                    f"MATCH (n:{label} {{id: $id}}) RETURN n.status AS status",
                    id=rec["id"],
                ).single()
                if existing is not None and existing["status"] != "candidate":
                    print(f"跳過：{label} '{rec['id']}' 已存在且非 candidate（不覆蓋既有資料）")
                    n_skipped += 1
                    continue

                props = {k: v for k, v in rec.items() if k not in SKIP_FIELDS and v is not None}
                props["status"] = "candidate"
                props["created_by"] = "llm_extraction"

                # label 已限制在白名單內，安全內插
                session.run(
                    f"MERGE (n:{label} {{id: $id}}) "
                    "ON CREATE SET n.created_at = $now "
                    "SET n += $props, n.updated_at = $now",
                    id=rec["id"], props=props, now=now,
                )
                n_created += 1
                print(f"寫入 candidate：{label} {rec['id']}（{rec.get('name')}）")
    finally:
        driver.close()

    print(f"完成：{n_created} 個節點候選已寫入（status=candidate），{n_skipped} 個略過。請至 /review 審核。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
