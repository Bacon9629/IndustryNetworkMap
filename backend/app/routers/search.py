from fastapi import APIRouter, Query

from ..db import run_query

router = APIRouter()

SEARCH_QUERY = """
MATCH (n)
WHERE (n:Company OR n:Product OR n:Industry OR n:Application)
  AND (toLower(n.name) CONTAINS toLower($q)
       OR toLower(coalesce(n.english_name, '')) CONTAINS toLower($q)
       OR coalesce(n.ticker, '') = $q
       OR any(a IN coalesce(n.aliases, []) WHERE toLower(a) CONTAINS toLower($q)))
RETURN n.id AS id, labels(n)[0] AS type, n.name AS name,
       n.english_name AS english_name, n.ticker AS ticker,
       n.exchange AS exchange, n.is_listed_in_tw AS is_listed_in_tw,
       n.description AS description
ORDER BY n.name
LIMIT $limit
"""


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    return {"query": q, "results": run_query(SEARCH_QUERY, q=q, limit=limit)}
