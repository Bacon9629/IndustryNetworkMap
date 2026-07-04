"""Import seed CSVs into Neo4j. Repeatable (MERGE-based): re-running never duplicates nodes or edges.

Usage (from ingestion/):
    python scripts/import_graph.py [--wipe] [--seeds seeds] [--uri bolt://localhost:7687]
Env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD override defaults.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.validate import NODE_FILES, REL_FILE, REL_TYPE_RULES, load_csv, validate  # noqa: E402

CONSTRAINTS_FILE = Path(__file__).resolve().parents[2] / "infra" / "neo4j" / "constraints.cypher"

NODE_LIST_FIELDS = {"aliases"}
REL_LIST_FIELDS = {"source_ids", "evidence_ids"}
BOOL_FIELDS = {"is_listed_in_tw"}
FLOAT_FIELDS = {"confidence"}


def clean_props(row: dict, list_fields: set[str]) -> dict:
    props = {}
    for k, v in row.items():
        v = (v or "").strip()
        if v == "":
            continue
        if k in list_fields:
            props[k] = [x.strip() for x in v.split(";") if x.strip()]
        elif k in BOOL_FIELDS:
            props[k] = v.lower() == "true"
        elif k in FLOAT_FIELDS:
            props[k] = float(v)
        else:
            props[k] = v
    return props


def apply_constraints(session) -> None:
    statements = [s.strip() for s in CONSTRAINTS_FILE.read_text(encoding="utf-8").split(";")]
    for stmt in statements:
        stmt = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("//")).strip()
        if stmt:
            session.run(stmt)


def import_nodes(session, seeds_dir: Path, now: str) -> int:
    count = 0
    for filename, (label, _) in NODE_FILES.items():
        for row in load_csv(seeds_dir / filename):
            props = clean_props(row, NODE_LIST_FIELDS)
            node_id = props.pop("id")
            session.run(
                f"MERGE (n:{label} {{id: $id}}) "
                "ON CREATE SET n.created_at = $now "
                "SET n += $props, n.updated_at = $now",
                id=node_id, props=props, now=now,
            )
            count += 1
    return count


def import_relationships(session, seeds_dir: Path, id_to_label: dict[str, str], now: str) -> int:
    count = 0
    for row in load_csv(seeds_dir / REL_FILE):
        props = clean_props(row, REL_LIST_FIELDS)
        props.setdefault("created_by", "manual_seed")
        rel_id = props.pop("id")
        rel_type = props.pop("type")
        from_id = props.pop("from_id")
        to_id = props.pop("to_id")
        from_label = id_to_label[from_id]
        to_label = id_to_label[to_id]
        # rel_type / labels are validated against whitelists, safe to interpolate
        session.run(
            f"MATCH (a:{from_label} {{id: $from_id}}), (b:{to_label} {{id: $to_id}}) "
            f"MERGE (a)-[r:{rel_type} {{id: $rel_id}}]->(b) "
            "ON CREATE SET r.created_at = $now "
            "SET r += $props, r.updated_at = $now",
            from_id=from_id, to_id=to_id, rel_id=rel_id, props=props, now=now,
        )
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Import seed CSVs into Neo4j.")
    parser.add_argument("--seeds", default=str(Path(__file__).resolve().parents[1] / "seeds"))
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "industrymap_dev"))
    parser.add_argument("--wipe", action="store_true", help="清空整個 graph 後重建")
    args = parser.parse_args()

    seeds_dir = Path(args.seeds)
    errors, id_to_label = validate(seeds_dir)
    if errors:
        print(f"驗證失敗，中止匯入。共 {len(errors)} 個錯誤：")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"驗證通過（{len(id_to_label)} 個節點 id）。連線 {args.uri} ...")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with driver.session() as session:
            if args.wipe:
                print("清空既有 graph ...")
                session.run("MATCH (n) DETACH DELETE n")
            apply_constraints(session)
            n_nodes = import_nodes(session, seeds_dir, now)
            n_rels = import_relationships(session, seeds_dir, id_to_label, now)
        print(f"匯入完成：{n_nodes} 個節點、{n_rels} 條關係（MERGE，重複執行安全）。")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
