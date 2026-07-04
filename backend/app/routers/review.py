from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import REL_TYPES
from ..db import run_query

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


LIST_QUERY = """
MATCH (a)-[r]->(b)
WHERE r.status = 'candidate'
  AND ($rel_type IS NULL OR type(r) = $rel_type)
  AND ($min_confidence IS NULL OR coalesce(r.confidence, 0) >= $min_confidence)
  AND ($created_by IS NULL OR r.created_by = $created_by)
OPTIONAL MATCH (s:Source) WHERE s.id IN coalesce(r.source_ids, [])
WITH a, r, b, collect(properties(s)) AS sources
ORDER BY coalesce(r.confidence, 0) DESC, r.id
SKIP $offset LIMIT $limit
RETURN r.id AS id, type(r) AS type, properties(r) AS props, sources,
       a.id AS from_id, a.name AS from_name, labels(a)[0] AS from_type,
       b.id AS to_id, b.name AS to_name, labels(b)[0] AS to_type
"""

COUNT_QUERY = """
MATCH ()-[r]->()
WHERE r.status = 'candidate'
  AND ($rel_type IS NULL OR type(r) = $rel_type)
  AND ($min_confidence IS NULL OR coalesce(r.confidence, 0) >= $min_confidence)
  AND ($created_by IS NULL OR r.created_by = $created_by)
RETURN count(r) AS total
"""


@router.get("/review/candidates")
def list_candidates(
    rel_type: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    created_by: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    if rel_type and rel_type not in REL_TYPES:
        raise HTTPException(status_code=400, detail=f"unknown relationship type '{rel_type}'")
    params = dict(rel_type=rel_type, min_confidence=min_confidence, created_by=created_by)
    total = run_query(COUNT_QUERY, **params)[0]["total"]
    rows = run_query(LIST_QUERY, **params, limit=limit, offset=offset)
    return {
        "total": total,
        "candidates": [
            {
                "id": r["id"],
                "type": r["type"],
                "from": {"id": r["from_id"], "name": r["from_name"], "type": r["from_type"]},
                "to": {"id": r["to_id"], "name": r["to_name"], "type": r["to_type"]},
                "properties": r["props"],
                "sources": r["sources"],
            }
            for r in rows
        ],
    }


class ReviewAction(BaseModel):
    review_note: str | None = None
    reviewed_by: str = "manual_review"


class CandidatePatch(BaseModel):
    confidence: float | None = Field(None, ge=0, le=1)
    note: str | None = None
    period: str | None = None


def _set_status(edge_id: str, new_status: str, body: ReviewAction) -> dict:
    rows = run_query(
        """
        MATCH ()-[r {id: $edge_id}]->()
        WHERE r.status = 'candidate'
        SET r.status = $new_status, r.reviewed_at = $now, r.reviewed_by = $reviewed_by,
            r.review_note = coalesce($review_note, r.review_note), r.updated_at = $now
        RETURN r.id AS id, r.status AS status
        """,
        edge_id=edge_id, new_status=new_status, now=_now(),
        reviewed_by=body.reviewed_by, review_note=body.review_note,
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"candidate edge '{edge_id}' not found（不存在或非 candidate）")
    return rows[0]


@router.post("/review/candidates/{edge_id}/accept")
def accept_candidate(edge_id: str, body: ReviewAction | None = None):
    return _set_status(edge_id, "verified", body or ReviewAction())


@router.post("/review/candidates/{edge_id}/reject")
def reject_candidate(edge_id: str, body: ReviewAction | None = None):
    return _set_status(edge_id, "rejected", body or ReviewAction())


@router.patch("/review/candidates/{edge_id}")
def patch_candidate(edge_id: str, body: CandidatePatch):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="沒有可更新的欄位")
    rows = run_query(
        """
        MATCH ()-[r {id: $edge_id}]->()
        WHERE r.status = 'candidate'
        SET r += $updates, r.updated_at = $now
        RETURN r.id AS id, properties(r) AS props
        """,
        edge_id=edge_id, updates=updates, now=_now(),
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"candidate edge '{edge_id}' not found（不存在或非 candidate）")
    return rows[0]
