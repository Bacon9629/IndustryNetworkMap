from fastapi import APIRouter, HTTPException

from ..db import run_query

router = APIRouter()

NODE_QUERY = """
MATCH (n {id: $id})
WHERE n:Company OR n:Product OR n:Industry OR n:Application OR n:Source OR n:Evidence
RETURN properties(n) AS props, labels(n)[0] AS type,
       COUNT { (n)-[]->() } AS out_degree,
       COUNT { (n)<-[]-() } AS in_degree
"""

NEIGHBOR_SUMMARY_QUERY = """
MATCH (n {id: $id})-[r]-(m)
RETURN type(r) AS rel_type,
       CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS direction,
       count(*) AS count
ORDER BY rel_type
"""


@router.get("/nodes/{node_id}")
def get_node(node_id: str):
    rows = run_query(NODE_QUERY, id=node_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"node '{node_id}' not found")
    row = rows[0]
    return {
        "id": node_id,
        "type": row["type"],
        "properties": row["props"],
        "out_degree": row["out_degree"],
        "in_degree": row["in_degree"],
        "relationship_summary": run_query(NEIGHBOR_SUMMARY_QUERY, id=node_id),
    }
