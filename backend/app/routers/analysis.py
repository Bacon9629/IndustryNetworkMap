from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_driver, run_query

router = APIRouter()

PATH_DECAY = {1: 1.0, 2: 0.7, 3: 0.5, 4: 0.3}

TRAVERSAL_TYPES = (
    "DRIVES_DEMAND_FOR|INCREASES_DEMAND_FOR|USED_IN|ENABLES|"
    "COMPONENT_OF|INPUT_OF|PRODUCES|SELLS|ASSEMBLES|"
    "SUPPLIES_TO|MANUFACTURES_FOR|ASSEMBLES_FOR"
)

DECREASE_TRAVERSAL_TYPES = TRAVERSAL_TYPES + "|DECREASES_DEMAND_FOR"

SUPPLY_TRAVERSAL_TYPES = (
    "SUPPLIES_TO|MANUFACTURES_FOR|ASSEMBLES_FOR|"
    "PRODUCES|SELLS|ASSEMBLES|USES|COMPONENT_OF|INPUT_OF"
)


class DemandShockRequest(BaseModel):
    target_node_id: str
    depth: int = Field(3, ge=1, le=4)
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    tw_only: bool = False
    limit: int = Field(30, ge=1, le=100)
    shock_direction: Literal["increase", "decrease"] = "increase"


@router.post("/analysis/demand-shock")
def demand_shock(req: DemandShockRequest):
    target = run_query(
        "MATCH (t {id: $id}) WHERE t:Application OR t:Product "
        "RETURN t.id AS id, t.name AS name, labels(t)[0] AS type",
        id=req.target_node_id,
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"target '{req.target_node_id}' not found (must be Application or Product)")

    traversal = DECREASE_TRAVERSAL_TYPES if req.shock_direction == "decrease" else TRAVERSAL_TYPES
    query = (
        "MATCH (t {id: $id}) WHERE t:Application OR t:Product "
        f"MATCH p = (t)-[:{traversal}*1..{req.depth}]-(c:Company) "
        "WHERE all(rel IN relationships(p) WHERE "
        "  coalesce(rel.confidence, 0.0) >= $min_confidence "
        "  AND coalesce(rel.status, '') <> 'rejected') "
        "  AND ($tw_only = false OR c.is_listed_in_tw = true) "
        "WITH c, p, "
        "  reduce(conf = 1.0, rel IN relationships(p) | conf * coalesce(rel.confidence, 0.5)) AS path_conf, "
        "  length(p) AS hops "
        "ORDER BY path_conf DESC "
        "WITH c, collect({ "
        "  path_conf: path_conf, hops: hops, "
        "  nodes: [n IN nodes(p) | {id: n.id, name: n.name, type: labels(n)[0]}], "
        "  edges: [r IN relationships(p) | {id: r.id, type: type(r), from: startNode(r).id, "
        "          to: endNode(r).id, confidence: r.confidence, status: r.status}] "
        "})[0] AS best "
        "RETURN c.id AS company_id, c.name AS name, c.ticker AS ticker, "
        "       c.exchange AS exchange, c.is_listed_in_tw AS is_listed_in_tw, best"
    )

    with get_driver().session() as session:
        rows = [r.data() for r in session.run(query, id=req.target_node_id, min_confidence=req.min_confidence, tw_only=req.tw_only)]

    results = []
    for row in rows:
        best = row["best"]
        hops = best["hops"]
        decay = PATH_DECAY.get(hops, 0.3)
        results.append({
            "company_id": row["company_id"],
            "name": row["name"],
            "ticker": row["ticker"],
            "exchange": row["exchange"],
            "is_listed_in_tw": row["is_listed_in_tw"],
            "score": round(best["path_conf"] * decay, 4),
            "factors": {
                "path_confidence": round(best["path_conf"], 4),
                "path_decay": decay,
                "hops": hops,
                # 尚無營收占比資料，exposure / demand_relevance 以 1.0 計，標記 unknown 避免假精確
                "exposure_score": "unknown",
                "demand_relevance": "unknown",
            },
            "path": best,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "target": target[0],
        "depth": req.depth,
        "min_confidence": req.min_confidence,
        "shock_direction": req.shock_direction,
        # decrease = 同傳導路徑、語意為「可能受害」
        "impact": "benefit" if req.shock_direction == "increase" else "hurt",
        "affected_companies": results[: req.limit],
    }


@router.get("/analysis/key-nodes")
def key_nodes(
    node_type: str | None = Query(None, pattern="^(Company|Product|Industry|Application)$"),
    limit: int = Query(20, ge=1, le=100),
):
    rows = run_query(
        """
        MATCH (n)
        WHERE labels(n)[0] IN ['Company', 'Product', 'Industry', 'Application']
          AND ($node_type IS NULL OR labels(n)[0] = $node_type)
        OPTIONAL MATCH (n)-[r]-()
        WHERE coalesce(r.status, '') <> 'rejected'
        WITH n,
             count(r) AS total_degree,
             sum(CASE WHEN startNode(r) = n THEN 1 ELSE 0 END) AS out_degree,
             sum(CASE WHEN endNode(r) = n THEN 1 ELSE 0 END) AS in_degree
        WHERE total_degree > 0
        ORDER BY total_degree DESC, n.id
        LIMIT $limit
        RETURN n.id AS id, n.name AS name, labels(n)[0] AS type, n.ticker AS ticker,
               total_degree, in_degree, out_degree
        """,
        node_type=node_type, limit=limit,
    )
    return {"node_type": node_type, "nodes": rows}


@router.get("/analysis/bottlenecks")
def bottlenecks(
    max_producers: int = Query(2, ge=1, le=5),
    limit: int = Query(30, ge=1, le=100),
):
    rows = run_query(
        """
        MATCH (p:Product)<-[r:PRODUCES]-(c:Company)
        WHERE coalesce(r.status, '') <> 'rejected'
        WITH p, collect(DISTINCT {id: c.id, name: c.name, ticker: c.ticker,
                                  is_listed_in_tw: c.is_listed_in_tw}) AS producers
        WHERE size(producers) <= $max_producers
        OPTIONAL MATCH (p)-[u:COMPONENT_OF|INPUT_OF|USED_IN]->()
        WHERE coalesce(u.status, '') <> 'rejected'
        WITH p, producers, count(u) AS downstream_usage
        ORDER BY downstream_usage DESC, size(producers) ASC, p.id
        LIMIT $limit
        RETURN p.id AS product_id, p.name AS name, producers,
               size(producers) AS producer_count, downstream_usage
        """,
        max_producers=max_producers, limit=limit,
    )
    return {"max_producers": max_producers, "bottlenecks": rows}


CONCENTRATION_QUERY = """
MATCH (c:Company {id: $id})%s(other:Company)
WHERE coalesce(r.status, '') <> 'rejected'
WITH other, count(r) AS edge_count, sum(coalesce(r.confidence, 0.5)) AS weight,
     collect({id: r.id, type: type(r), confidence: r.confidence, product_id: r.product_id}) AS edges
ORDER BY weight DESC
RETURN other.id AS company_id, other.name AS name, other.ticker AS ticker,
       edge_count, weight, edges
"""


def _concentration_side(company_id: str, pattern: str) -> list[dict]:
    rows = run_query(CONCENTRATION_QUERY % pattern, id=company_id)
    total = sum(r["weight"] for r in rows) or 1.0
    return [
        {
            "company_id": r["company_id"],
            "name": r["name"],
            "ticker": r["ticker"],
            "edge_count": r["edge_count"],
            "weight": round(r["weight"], 4),
            "share": round(r["weight"] / total, 4),
            "edges": r["edges"],
        }
        for r in rows
    ]


@router.get("/analysis/concentration")
def concentration(company_id: str):
    found = run_query("MATCH (c:Company {id: $id}) RETURN c.id AS id, c.name AS name", id=company_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"company '{company_id}' not found")
    suppliers = _concentration_side(company_id, "<-[r:SUPPLIES_TO|MANUFACTURES_FOR|ASSEMBLES_FOR]-")
    customers = _concentration_side(company_id, "-[r:SUPPLIES_TO|MANUFACTURES_FOR|ASSEMBLES_FOR]->")
    return {
        "company": found[0],
        # 無營收占比資料：share 以關係數 × confidence 加權計算，非實際營收集中度
        "basis": "edge_count_confidence_weighted",
        "revenue_share": "unknown",
        "suppliers": suppliers,
        "customers": customers,
    }


class SupplyDisruptionRequest(BaseModel):
    target_node_id: str
    depth: int = Field(3, ge=1, le=4)
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    tw_only: bool = False
    limit: int = Field(30, ge=1, le=100)


@router.post("/analysis/supply-disruption")
def supply_disruption(req: SupplyDisruptionRequest):
    target = run_query(
        "MATCH (t {id: $id}) WHERE t:Company OR t:Product "
        "RETURN t.id AS id, t.name AS name, labels(t)[0] AS type",
        id=req.target_node_id,
    )
    if not target:
        raise HTTPException(status_code=404, detail=f"target '{req.target_node_id}' not found (must be Company or Product)")

    query = (
        "MATCH (t {id: $id}) WHERE t:Company OR t:Product "
        f"MATCH p = (t)-[:{SUPPLY_TRAVERSAL_TYPES}*1..{req.depth}]-(c:Company) "
        "WHERE c.id <> $id "
        "  AND all(rel IN relationships(p) WHERE "
        "  coalesce(rel.confidence, 0.0) >= $min_confidence "
        "  AND coalesce(rel.status, '') <> 'rejected') "
        "  AND ($tw_only = false OR c.is_listed_in_tw = true) "
        "WITH c, p, "
        "  reduce(conf = 1.0, rel IN relationships(p) | conf * coalesce(rel.confidence, 0.5)) AS path_conf, "
        "  length(p) AS hops "
        "ORDER BY path_conf DESC "
        "WITH c, collect({ "
        "  path_conf: path_conf, hops: hops, "
        "  nodes: [n IN nodes(p) | {id: n.id, name: n.name, type: labels(n)[0]}], "
        "  edges: [r IN relationships(p) | {id: r.id, type: type(r), from: startNode(r).id, "
        "          to: endNode(r).id, confidence: r.confidence, status: r.status}] "
        "})[0] AS best "
        "RETURN c.id AS company_id, c.name AS name, c.ticker AS ticker, "
        "       c.exchange AS exchange, c.is_listed_in_tw AS is_listed_in_tw, best"
    )

    with get_driver().session() as session:
        rows = [r.data() for r in session.run(
            query, id=req.target_node_id, min_confidence=req.min_confidence, tw_only=req.tw_only
        )]

    product_ids = {
        n["id"]
        for row in rows
        for n in row["best"]["nodes"]
        if n["type"] == "Product"
    }
    alt_products: set[str] = set()
    if product_ids:
        alt_rows = run_query(
            """
            MATCH (p:Product) WHERE p.id IN $ids
            OPTIONAL MATCH (p)-[s:SUBSTITUTE_FOR]-()
            WHERE coalesce(s.status, '') <> 'rejected'
            OPTIONAL MATCH (p)<-[pr:PRODUCES]-(maker:Company)
            WHERE coalesce(pr.status, '') <> 'rejected' AND maker.id <> $target_id
            WITH p, count(DISTINCT s) AS substitutes, count(DISTINCT maker) AS other_makers
            RETURN p.id AS id, substitutes, other_makers
            """,
            ids=list(product_ids), target_id=req.target_node_id,
        )
        # 公司中斷：該產品另有 ≥1 家生產者即有替代來源；產品中斷：需 ≥2 家生產者或有 SUBSTITUTE_FOR
        min_other_makers = 1 if target[0]["type"] == "Company" else 2
        alt_products = {
            r["id"] for r in alt_rows
            if r["substitutes"] > 0 or r["other_makers"] >= min_other_makers
        }

    results = []
    for row in rows:
        best = row["best"]
        hops = best["hops"]
        decay = PATH_DECAY.get(hops, 0.3)
        path_products = [n["id"] for n in best["nodes"] if n["type"] == "Product"]
        results.append({
            "company_id": row["company_id"],
            "name": row["name"],
            "ticker": row["ticker"],
            "exchange": row["exchange"],
            "is_listed_in_tw": row["is_listed_in_tw"],
            "score": round(best["path_conf"] * decay, 4),
            "has_alternative": any(pid in alt_products for pid in path_products),
            "factors": {
                "path_confidence": round(best["path_conf"], 4),
                "path_decay": decay,
                "hops": hops,
                "exposure_score": "unknown",
            },
            "path": best,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "target": target[0],
        "depth": req.depth,
        "min_confidence": req.min_confidence,
        "impact": "disruption",
        "affected_companies": results[: req.limit],
    }
