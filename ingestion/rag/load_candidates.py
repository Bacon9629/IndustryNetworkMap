"""Load extracted candidate relationships into Neo4j.

Usage (from ingestion/):
    python rag/load_candidates.py [--candidates rag/extracted/candidates.jsonl]

Loaded relationships are always status=candidate and created_by=llm_extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.validate import FORBIDDEN_TYPES, REL_TYPE_RULES  # noqa: E402

VALID_LABELS = {"Company", "Product", "Industry", "Application"}


def candidate_id(rec: dict) -> str:
    key = f"{rec['from_id']}|{rec['type']}|{rec['to_id']}|{rec['chunk_id']}"
    return "llm_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def node_exists(session, label: str, node_id: str) -> bool:
    if label not in VALID_LABELS:
        return False
    row = session.run(f"MATCH (n:{label} {{id: $id}}) RETURN count(n) AS n", id=node_id).single()
    return bool(row and row["n"])


def source_exists(session, source_id: str) -> bool:
    row = session.run("MATCH (s:Source {id: $id}) RETURN count(s) AS n", id=source_id).single()
    return bool(row and row["n"])


def validate_records(session, records: list[dict]) -> list[str]:
    errors: list[str] = []
    required = {
        "from_id",
        "from_label",
        "to_id",
        "to_label",
        "type",
        "evidence",
        "confidence",
        "source_id",
        "chunk_id",
    }
    seen_keys: set[tuple[str, str, str, str]] = set()
    source_cache: dict[str, bool] = {}
    node_cache: dict[tuple[str, str], bool] = {}

    for i, rec in enumerate(records, start=1):
        missing = sorted(key for key in required if rec.get(key) in {None, ""})
        if missing:
            errors.append(f"row {i}: missing required fields {missing}")
            continue

        key = (rec["from_id"], rec["type"], rec["to_id"], rec["chunk_id"])
        if key in seen_keys:
            errors.append(f"row {i}: duplicate candidate key {key}")
        seen_keys.add(key)

        rel_type = rec["type"]
        if rel_type in FORBIDDEN_TYPES or rel_type not in REL_TYPE_RULES:
            errors.append(f"row {i}: relationship type '{rel_type}' is not allowed")
            continue

        allowed_from, allowed_to = REL_TYPE_RULES[rel_type]
        if rec["from_label"] not in allowed_from:
            errors.append(f"row {i}: {rel_type} cannot start from {rec['from_label']}")
        if rec["to_label"] not in allowed_to:
            errors.append(f"row {i}: {rel_type} cannot point to {rec['to_label']}")

        try:
            confidence = float(rec["confidence"])
        except (TypeError, ValueError):
            errors.append(f"row {i}: confidence is not numeric")
        else:
            if not 0.0 <= confidence <= 0.8:
                errors.append(f"row {i}: confidence {confidence} must be between 0 and 0.8")

        source_id = rec["source_id"]
        if source_id not in source_cache:
            source_cache[source_id] = source_exists(session, source_id)
        if not source_cache[source_id]:
            errors.append(f"row {i}: source_id '{source_id}' does not exist")

        for side, label_key, id_key in (
            ("from", "from_label", "from_id"),
            ("to", "to_label", "to_id"),
        ):
            node_key = (rec[label_key], rec[id_key])
            if node_key not in node_cache:
                node_cache[node_key] = node_exists(session, rec[label_key], rec[id_key])
            if not node_cache[node_key]:
                errors.append(f"row {i}: {side} node '{rec[id_key]}' with label {rec[label_key]} does not exist")

        product_id = rec.get("product_id")
        if product_id:
            node_key = ("Product", product_id)
            if node_key not in node_cache:
                node_cache[node_key] = node_exists(session, "Product", product_id)
            if not node_cache[node_key]:
                errors.append(f"row {i}: product_id '{product_id}' does not exist")

    return errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", default=str(Path(__file__).parent / "extracted" / "candidates.jsonl"))
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "industrymap_dev"))
    parser.add_argument("--dry-run", action="store_true", help="Validate candidate records without writing to Neo4j.")
    args = parser.parse_args()

    records = [json.loads(line) for line in Path(args.candidates).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise SystemExit("No candidate records found. Run extract.py first.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    n = 0
    try:
        with driver.session() as session:
            errors = validate_records(session, records)
            if errors:
                print(f"Candidate validation failed with {len(errors)} error(s):")
                for error in errors[:100]:
                    print(f"  - {error}")
                return 1
            if args.dry_run:
                print(f"Dry run OK: {len(records)} candidate records validated against Neo4j.")
                return 0
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

                session.run(
                    f"MATCH (a:{rec['from_label']} {{id: $from_id}}), (b:{rec['to_label']} {{id: $to_id}}) "
                    f"MERGE (a)-[r:{rec['type']} {{id: $rel_id}}]->(b) "
                    "ON CREATE SET r.created_at = $now "
                    "SET r += $props, r.updated_at = $now",
                    from_id=rec["from_id"],
                    to_id=rec["to_id"],
                    rel_id=candidate_id(rec),
                    props=props,
                    now=now,
                )
                n += 1
        print(f"Loaded {n} candidate relationships into Neo4j. Review them in /review before verification.")
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
