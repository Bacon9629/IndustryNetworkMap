"""LLM node/entity candidate extraction from unresolved entities (OpenAI structured output).

Usage (from ingestion/):
    python rag/extract_entities.py [--unresolved rag/extracted/unresolved_entities.jsonl]
                                    [--chunks rag/chunks/chunks.jsonl]
                                    [--out rag/extracted/node_candidates.jsonl]
Requires OPENAI_API_KEY. Output is NOT written to Neo4j here — see load_node_candidates.py.

規則（鐵律，見 docs/development/data-model.md「節點審核欄位」）：
- 只輸出 candidate 節點；不寫 verified。
- 只能輸出原文明確支持的欄位；無法確認一律 null，禁止臆測 ticker / exchange 等。
- label 依 docs/development/relationship-types.md 的合法 from/to 型別推斷（同一實體可能出現在多筆
  unresolved 紀錄，取多數決；仍有歧義則交給 LLM 依上下文判斷）。
- Company 無法確認 ticker + exchange → 無法組出合法 id，落到 node_needs_manual_review.jsonl，不入庫。
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validators.validate import NODE_FILES, REL_TYPE_RULES  # noqa: E402

from llm_client import DEFAULT_MODEL, get_client  # noqa: E402

LABELS = ["Company", "Product", "Industry", "Application"]
REQUIRED_FIELDS = {label: set(fields) - {"id"} for label, fields in
                   {v[0]: v[1] for v in NODE_FILES.values()}.items()}

ENTITY_SCHEMA = {
    "name": "entity_extraction",
    "schema": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": LABELS, "description": "從候選型別中選一個最符合上下文的"},
            "name": {"type": "string", "description": "實體的正式中文或原文名稱"},
            "aliases": {"type": "array", "items": {"type": "string"}},
            "description": {"type": ["string", "null"]},
            "ticker": {"type": ["string", "null"], "description": "僅 label=Company 適用；原文未明載就填 null"},
            "exchange": {"type": ["string", "null"], "description": "僅 label=Company 適用，例如 TWSE/TPEX/US/KR/NL；原文未明載就填 null"},
            "country": {"type": ["string", "null"], "description": "僅 label=Company 適用"},
            "is_listed_in_tw": {"type": ["boolean", "null"], "description": "僅 label=Company 適用；不確定就填 null"},
            "category": {"type": ["string", "null"], "description": "僅 label=Product 適用，例如 Semiconductor/Equipment/Component/Material/Service/End Device"},
            "suggested_id": {
                "type": ["string", "null"],
                "description": "僅 label=Product/Industry/Application 適用；小寫 snake_case 英文語意 id，例如 smart_meter",
            },
            "evidence": {"type": "string", "description": "原文中支持此實體存在的句子（逐字引用）"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "label", "name", "aliases", "description", "ticker", "exchange", "country",
            "is_listed_in_tw", "category", "suggested_id", "evidence", "confidence",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}

SYSTEM_PROMPT = """你是產業鏈實體抽取器。任務：確認一個在既有 graph 中找不到的實體是否真實存在於原文，並抽取其屬性。
規則：
1. 只能使用原文明確支持的資訊；不確定的欄位一律填 null，禁止臆測 ticker、exchange、is_listed_in_tw 等。
2. evidence 必須逐字引用原文句子，禁止編造或改寫。
3. confidence：原文直接陳述 0.5-0.8；原文帶「市場報導/推測」字眼 0.3-0.5。抽取結果一律是待人工審核的 candidate，不要給超過 0.8。
4. label 只能從系統提供的候選型別清單中選擇，依上下文語意判斷最合理的一個。
5. suggested_id 只在 label 為 Product/Industry/Application 時提供，須為小寫英文 snake_case 語意 slug。"""


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return s


def candidate_labels(rec: dict, side: str) -> set[str]:
    """從 relationship type 的合法 from/to 型別推斷未解析實體可能的 label。"""
    rel_type = rec.get("type")
    rule = REL_TYPE_RULES.get(rel_type)
    if not rule:
        return set(LABELS)
    allowed_from, allowed_to = rule
    allowed = allowed_from if side == "from" else allowed_to
    return {label for label in allowed if label in LABELS} or set(LABELS)


def collect_unresolved(records: list[dict]) -> dict[str, dict]:
    """依名稱聚合未解析實體：可能的 label 票選、evidence、來源 chunk。"""
    grouped: dict[str, dict] = {}
    for rec in records:
        for side in ("from", "to"):
            if rec.get(f"{side}_resolved"):
                continue
            name = (rec.get(f"{side}_name") or "").strip()
            if not name:
                continue
            entry = grouped.setdefault(name, {
                "label_votes": Counter(), "chunk_ids": set(), "evidence": set(), "source_ids": set(),
            })
            entry["label_votes"].update(candidate_labels(rec, side))
            if rec.get("chunk_id"):
                entry["chunk_ids"].add(rec["chunk_id"])
            if rec.get("evidence"):
                entry["evidence"].add(rec["evidence"])
            if rec.get("source_id"):
                entry["source_ids"].add(rec["source_id"])
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unresolved", default=str(Path(__file__).parent / "extracted" / "unresolved_entities.jsonl"))
    parser.add_argument("--chunks", default=str(Path(__file__).parent / "chunks" / "chunks.jsonl"))
    parser.add_argument("--out", default=str(Path(__file__).parent / "extracted" / "node_candidates.jsonl"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    unresolved_path = Path(args.unresolved)
    if not unresolved_path.exists():
        raise SystemExit(f"{unresolved_path} 不存在，請先執行 rag/extract.py 產生未解析實體清單")
    records = [json.loads(line) for line in unresolved_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        print("沒有未解析實體，無需抽取節點候選。")
        return 0

    chunks_by_id: dict[str, str] = {}
    chunks_path = Path(args.chunks)
    if chunks_path.exists():
        for line in chunks_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            chunks_by_id[c["chunk_id"]] = c["text"]

    grouped = collect_unresolved(records)
    client = get_client()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manual_path = out_path.parent / "node_needs_manual_review.jsonl"

    n_ok = n_manual = n_invalid = 0
    with open(out_path, "w", encoding="utf-8") as out, open(manual_path, "w", encoding="utf-8") as manual:
        for name, info in grouped.items():
            allowed_labels = {label for label, count in info["label_votes"].most_common()
                               if count == info["label_votes"].most_common(1)[0][1]}
            context_text = "\n---\n".join(
                chunks_by_id[cid] for cid in list(info["chunk_ids"])[:3] if cid in chunks_by_id
            ) or "\n".join(info["evidence"])
            user_msg = (
                f"候選型別（label 只能從中選一個）：{sorted(allowed_labels)}\n"
                f"待確認實體名稱：{name}\n"
                f"原文段落：\n{context_text}"
            )
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_schema", "json_schema": ENTITY_SCHEMA},
            )
            ent = json.loads(resp.choices[0].message.content)

            label = ent["label"]
            if label not in allowed_labels:
                n_invalid += 1
                continue

            common = {
                "label": label,
                "name": ent["name"] or name,
                "aliases": [a for a in ent.get("aliases") or [] if a],
                "description": ent.get("description"),
                "evidence": ent["evidence"],
                "confidence": min(float(ent["confidence"]), 0.8),
                "source_ids": sorted(info["source_ids"]),
                "chunk_ids": sorted(info["chunk_ids"]),
            }

            if label == "Company":
                ticker, exchange = ent.get("ticker"), ent.get("exchange")
                if not ticker or not exchange:
                    manual.write(json.dumps({**common, "reason": "缺少 ticker 或 exchange，無法組出合法 id"},
                                             ensure_ascii=False) + "\n")
                    n_manual += 1
                    continue
                node_id = f"{exchange.strip().upper()}_{ticker.strip().upper()}"
                is_listed = ent.get("is_listed_in_tw")
                if is_listed is None:
                    is_listed = exchange.strip().upper() in {"TWSE", "TPEX"}
                common.update({
                    "id": node_id, "ticker": ticker.strip(), "exchange": exchange.strip().upper(),
                    "country": ent.get("country"), "is_listed_in_tw": bool(is_listed),
                })
            else:
                suggested = ent.get("suggested_id") or slugify(name)
                node_id = slugify(suggested)
                if not node_id:
                    manual.write(json.dumps({**common, "reason": "無法產生合法 id slug"},
                                             ensure_ascii=False) + "\n")
                    n_manual += 1
                    continue
                common["id"] = node_id
                if label == "Product":
                    common["category"] = ent.get("category") or "unknown"

            missing = [
                f for f in REQUIRED_FIELDS.get(label, set())
                if not isinstance(common.get(f), bool) and not str(common.get(f, "")).strip()
            ]
            if missing:
                manual.write(json.dumps({**common, "reason": f"缺少必要欄位：{missing}"}, ensure_ascii=False) + "\n")
                n_manual += 1
                continue

            out.write(json.dumps(common, ensure_ascii=False) + "\n")
            n_ok += 1
            print(f"{name} → {label} candidate（id={common['id']}）")

    print(f"完成：{n_ok} 個節點候選可入庫、{n_manual} 個需人工建立（見 {manual_path.name}）、{n_invalid} 個型別不合規則已丟棄。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
