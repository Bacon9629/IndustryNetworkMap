"""LLM relationship extraction from chunks (OpenAI structured output).

Usage (from ingestion/):
    python rag/extract.py [--chunks rag/chunks/chunks.jsonl] [--out rag/extracted/candidates.jsonl]
Requires OPENAI_API_KEY. Output is NOT written to Neo4j here — see load_candidates.py.

規則（鐵律）：
- 只輸出 candidate；不寫 verified。
- type 必須在 REL_TYPE_RULES 白名單內，且 from/to 節點類型合法（重用 validators/validate.py）。
- 節點解析不到既有 id 的關係不入庫，輸出到 unresolved 清單供人工建節點。
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.validate import FORBIDDEN_TYPES, REL_TYPE_RULES  # noqa: E402

from llm_client import DEFAULT_MODEL, get_client  # noqa: E402

# graph 關係抽取不含 SUPPORTED_BY / FROM_SOURCE（那是 evidence 機制）
EXTRACTABLE_TYPES = sorted(t for t in REL_TYPE_RULES if t not in {"SUPPORTED_BY", "FROM_SOURCE"})

EXTRACTION_SCHEMA = {
    "name": "relationship_extraction",
    "schema": {
        "type": "object",
        "properties": {
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from_name": {"type": "string", "description": "來源實體名稱（公司/產品/產業/應用，用原文名稱）"},
                        "to_name": {"type": "string", "description": "目標實體名稱"},
                        "type": {"type": "string", "enum": EXTRACTABLE_TYPES},
                        "product": {"type": ["string", "null"], "description": "關係涉及的產品名稱（若有）"},
                        "evidence": {"type": "string", "description": "原文中支持此關係的句子（逐字引用）"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "period": {"type": ["string", "null"]},
                    },
                    "required": ["from_name", "to_name", "type", "product", "evidence", "confidence", "period"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["relationships"],
        "additionalProperties": False,
    },
    "strict": True,
}

SYSTEM_PROMPT = f"""你是產業鏈關係抽取器。從文字中抽取明確、有方向的關係。
規則：
1. 只抽取原文明確支持的關係，evidence 必須逐字引用原文句子，禁止編造。
2. type 只能用：{", ".join(EXTRACTABLE_TYPES)}。禁止模糊關係（RELATED_TO 等）。
3. confidence：原文直接陳述 0.6-0.8；原文帶「市場報導/推測」字眼 0.4-0.6。抽取結果一律是待人工審核的 candidate，不要給超過 0.8。
4. 抽不到就回空陣列，不要硬湊。"""


def resolve_node(session, name: str) -> dict | None:
    rows = session.run(
        """
        MATCH (n) WHERE labels(n)[0] IN ['Company', 'Product', 'Industry', 'Application']
          AND (n.name = $name OR n.english_name = $name OR n.ticker = $name
               OR $name IN coalesce(n.aliases, []) OR toLower(n.name) = toLower($name))
        RETURN n.id AS id, n.name AS name, labels(n)[0] AS label LIMIT 1
        """,
        name=name.strip(),
    ).single()
    return dict(rows) if rows else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "extracted" / "candidates.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    client = get_client()

    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ.get("NEO4J_PASSWORD", "industrymap_dev")),
    )

    records = [json.loads(line) for line in Path(args.chunks).read_text(encoding="utf-8").splitlines() if line.strip()]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    unresolved_path = out_path.parent / "unresolved_entities.jsonl"

    n_ok = n_unresolved = n_invalid = 0
    with open(out_path, "w", encoding="utf-8") as out, \
         open(unresolved_path, "w", encoding="utf-8") as unres, \
         driver.session() as session:
        for rec in records:
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": rec["text"]},
                ],
                response_format={"type": "json_schema", "json_schema": EXTRACTION_SCHEMA},
            )
            rels = json.loads(resp.choices[0].message.content)["relationships"]
            for rel in rels:
                rel_type = rel["type"]
                if rel_type in FORBIDDEN_TYPES or rel_type not in REL_TYPE_RULES:
                    n_invalid += 1
                    continue
                # docs/development/relationship-types.md：BUYS_FROM 避免使用，反向改建 SUPPLIES_TO
                if rel_type == "BUYS_FROM":
                    rel_type = "SUPPLIES_TO"
                    rel["from_name"], rel["to_name"] = rel["to_name"], rel["from_name"]
                frm = resolve_node(session, rel["from_name"])
                to = resolve_node(session, rel["to_name"])
                if not frm or not to:
                    unres.write(json.dumps({**rel, "chunk_id": rec["chunk_id"],
                                            "from_resolved": frm, "to_resolved": to}, ensure_ascii=False) + "\n")
                    n_unresolved += 1
                    continue
                allowed_from, allowed_to = REL_TYPE_RULES[rel_type]
                if frm["label"] not in allowed_from or to["label"] not in allowed_to:
                    n_invalid += 1
                    continue
                product = resolve_node(session, rel["product"]) if rel.get("product") else None
                out.write(json.dumps({
                    "from_id": frm["id"], "from_label": frm["label"],
                    "to_id": to["id"], "to_label": to["label"],
                    "type": rel_type,
                    "product_id": product["id"] if product and product["label"] == "Product" else None,
                    "evidence": rel["evidence"],
                    "confidence": min(float(rel["confidence"]), 0.8),
                    "period": rel.get("period") or rec.get("period"),
                    "source_id": rec["source_id"],
                    "chunk_id": rec["chunk_id"],
                }, ensure_ascii=False) + "\n")
                n_ok += 1
            print(f"{rec['chunk_id']}: {len(rels)} 條抽出")

    driver.close()
    print(f"完成：{n_ok} 條可入庫 candidate、{n_unresolved} 條節點未解析（見 {unresolved_path.name}）、{n_invalid} 條不合規則已丟棄。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
