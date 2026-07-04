from fastapi import APIRouter, HTTPException

from ..db import get_driver, run_query

router = APIRouter()

EDGE_QUERY = """
MATCH (a)-[r {id: $edge_id}]->(b)
RETURN properties(r) AS props, type(r) AS type,
       a.id AS from_id, a.name AS from_name, labels(a)[0] AS from_type,
       b.id AS to_id, b.name AS to_name, labels(b)[0] AS to_type
"""

SOURCES_QUERY = """
MATCH (s:Source) WHERE s.id IN $source_ids
RETURN properties(s) AS source
"""


@router.get("/edges/{edge_id}")
def get_edge(edge_id: str):
    rows = run_query(EDGE_QUERY, edge_id=edge_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"edge '{edge_id}' not found")
    row = rows[0]
    props = row["props"]
    source_ids = props.get("source_ids", []) or []
    sources = [r["source"] for r in run_query(SOURCES_QUERY, source_ids=source_ids)] if source_ids else []

    evidence = []
    if props.get("evidence_ids"):
        evidence = [
            r["ev"]
            for r in run_query(
                "MATCH (e:Evidence) WHERE e.id IN $ids RETURN properties(e) AS ev",
                ids=props["evidence_ids"],
            )
        ]

    return {
        "id": edge_id,
        "type": row["type"],
        "from": {"id": row["from_id"], "name": row["from_name"], "type": row["from_type"]},
        "to": {"id": row["to_id"], "name": row["to_name"], "type": row["to_type"]},
        "properties": props,
        "sources": sources,
        "evidence": evidence,
    }
