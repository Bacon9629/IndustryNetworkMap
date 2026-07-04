from fastapi import APIRouter, HTTPException, Query

from ..config import REL_TYPES
from ..db import get_driver, run_query

router = APIRouter()

# upstream = incoming edges, downstream = outgoing edges
# (edge conventions: supplier -[:SUPPLIES_TO]-> customer, see docs/development/relationship-types.md)
ARROWS = {"upstream": ("<-", "-"), "downstream": ("-", "->"), "both": ("-", "-")}


def node_dict(n) -> dict:
    return {
        "id": n["id"],
        "type": list(n.labels)[0],
        "name": n.get("name"),
        "ticker": n.get("ticker"),
        "is_listed_in_tw": n.get("is_listed_in_tw"),
        "category": n.get("category"),
        "status": n.get("status"),
    }


def edge_dict(r) -> dict:
    return {
        "id": r.get("id"),
        "type": r.type,
        "from": r.start_node["id"],
        "to": r.end_node["id"],
        "description": r.get("description"),
        "confidence": r.get("confidence"),
        "status": r.get("status"),
        "period": r.get("period"),
        "product_id": r.get("product_id"),
    }


@router.get("/graph/neighborhood")
def neighborhood(
    node_id: str,
    depth: int = Query(1, ge=1, le=3),
    direction: str = Query("both", pattern="^(upstream|downstream|both)$"),
    relationship_types: str | None = None,
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    status: str | None = None,
):
    center = run_query(
        "MATCH (n {id: $id}) WHERE n:Company OR n:Product OR n:Industry OR n:Application "
        "RETURN n.id AS id LIMIT 1",
        id=node_id,
    )
    if not center:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")

    type_filter = ""
    if relationship_types:
        types = [t.strip().upper() for t in relationship_types.split(",") if t.strip()]
        invalid = [t for t in types if t not in REL_TYPES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"invalid relationship types: {invalid}")
        type_filter = ":" + "|".join(types)

    left, right = ARROWS[direction]
    query = (
        f"MATCH p = (c {{id: $id}}){left}[{type_filter}*1..{depth}]{right}(m) "
        "WHERE all(rel IN relationships(p) WHERE "
        "  ($min_confidence IS NULL OR coalesce(rel.confidence, 0.0) >= $min_confidence) "
        "  AND ($status IS NULL OR rel.status = $status) "
        "  AND coalesce(rel.status, '') <> 'rejected') "
        "  AND all(n IN nodes(p) WHERE coalesce(n.status, '') <> 'rejected') "
        "UNWIND nodes(p) AS n UNWIND relationships(p) AS r "
        "RETURN collect(DISTINCT n) AS nodes, collect(DISTINCT r) AS rels"
    )

    with get_driver().session() as session:
        record = session.run(query, id=node_id, min_confidence=min_confidence, status=status).single()

    nodes = [node_dict(n) for n in (record["nodes"] if record else [])]
    edges = [edge_dict(r) for r in (record["rels"] if record else [])]
    if not any(n["id"] == node_id for n in nodes):
        center_full = run_query(
            "MATCH (n {id: $id}) RETURN n.id AS id, labels(n)[0] AS type, n.name AS name, "
            "n.ticker AS ticker, n.is_listed_in_tw AS is_listed_in_tw, n.category AS category, "
            "n.status AS status",
            id=node_id,
        )
        nodes = center_full + nodes

    return {
        "center": node_id,
        "depth": depth,
        "direction": direction,
        "nodes": nodes,
        "edges": edges,
    }
