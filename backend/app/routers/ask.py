"""自然語言查詢：LLM 解析 intent → 呼叫既有分析 → LLM 生成中文解釋（引用實際路徑，不得編造）。"""

import json
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import run_query
from .analysis import (
    DemandShockRequest,
    SupplyDisruptionRequest,
    bottlenecks,
    demand_shock,
    key_nodes,
    supply_disruption,
)

router = APIRouter()

INTENT_SCHEMA = {
    "name": "question_intent",
    "schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["demand_shock_increase", "demand_shock_decrease", "supply_disruption", "bottleneck", "key_nodes", "unknown"],
            },
            "target_name": {"type": ["string", "null"], "description": "問題針對的公司/產品/應用名稱，原文照抄；bottleneck/key_nodes 可為 null"},
        },
        "required": ["intent", "target_name"],
        "additionalProperties": False,
    },
    "strict": True,
}

INTENT_PROMPT = """你是台股產業鏈分析系統的意圖解析器。將使用者問題分類為：
- demand_shock_increase：某產品/應用需求增加，誰受益
- demand_shock_decrease：某產品/應用需求下降，誰受害
- supply_disruption：某公司/產品供給中斷，誰受影響
- bottleneck：供應鏈瓶頸（生產者少的產品）
- key_nodes：產業鏈中最關鍵/連結最多的節點
- unknown：無法對應以上任何一種
target_name 用問題原文中的名稱，不要翻譯或改寫。"""

ANSWER_PROMPT = """你是台股產業鏈分析助理。根據系統提供的 graph 分析結果，用繁體中文簡潔回答使用者問題。
嚴格規則：
1. 只能引用分析結果中實際存在的公司、路徑與 confidence 數字，禁止編造任何未出現的資訊。
2. 說明每家關鍵公司時附上傳導路徑與 score。
3. candidate 狀態的關係要註明「未經審核」。
4. 分析結果為空就直說 graph 中查無資料，不要推測。"""


class AskRequest(BaseModel):
    question: str


def _client():
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="自然語言查詢需要 OPENAI_API_KEY 環境變數（目前未設定）")
    from openai import OpenAI
    return OpenAI()


MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def _resolve(name: str, labels: list[str]) -> dict | None:
    rows = run_query(
        """
        MATCH (n) WHERE labels(n)[0] IN $labels
          AND (toLower(n.name) CONTAINS toLower($q)
               OR toLower(coalesce(n.english_name, '')) CONTAINS toLower($q)
               OR coalesce(n.ticker, '') = $q
               OR any(a IN coalesce(n.aliases, []) WHERE toLower(a) CONTAINS toLower($q)))
        RETURN n.id AS id, n.name AS name, labels(n)[0] AS type
        ORDER BY size(n.name) LIMIT 1
        """,
        q=name.strip(), labels=labels,
    )
    return rows[0] if rows else None


@router.post("/ask")
def ask(req: AskRequest):
    client = _client()

    intent_resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": req.question},
        ],
        response_format={"type": "json_schema", "json_schema": INTENT_SCHEMA},
    )
    parsed = json.loads(intent_resp.choices[0].message.content)
    intent, target_name = parsed["intent"], parsed.get("target_name")

    if intent == "unknown":
        return {"answer": "這個問題超出目前支援的分析類型（需求變動 / 供應中斷 / 瓶頸 / 關鍵節點）。", "intent": intent, "evidence_paths": []}

    evidence_paths: list = []
    if intent in {"demand_shock_increase", "demand_shock_decrease"}:
        target = _resolve(target_name or "", ["Application", "Product"])
        if not target:
            raise HTTPException(status_code=404, detail=f"graph 中找不到目標「{target_name}」（需為產品或應用）")
        result = demand_shock(DemandShockRequest(
            target_node_id=target["id"], tw_only=True,
            shock_direction="decrease" if intent.endswith("decrease") else "increase",
        ))
        analysis_data = result["affected_companies"][:10]
        evidence_paths = [c["path"] for c in analysis_data]
    elif intent == "supply_disruption":
        target = _resolve(target_name or "", ["Company", "Product"])
        if not target:
            raise HTTPException(status_code=404, detail=f"graph 中找不到目標「{target_name}」（需為公司或產品）")
        result = supply_disruption(SupplyDisruptionRequest(target_node_id=target["id"], tw_only=True))
        analysis_data = result["affected_companies"][:10]
        evidence_paths = [c["path"] for c in analysis_data]
    elif intent == "bottleneck":
        result = bottlenecks(max_producers=2, limit=15)
        analysis_data = result["bottlenecks"]
    else:  # key_nodes
        result = key_nodes(node_type=None, limit=15)
        analysis_data = result["nodes"]

    answer_resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANSWER_PROMPT},
            {"role": "user", "content": (
                f"使用者問題：{req.question}\n\n"
                f"分析類型：{intent}\n\n"
                f"graph 分析結果（JSON）：\n{json.dumps(analysis_data, ensure_ascii=False)}"
            )},
        ],
    )

    return {
        "answer": answer_resp.choices[0].message.content,
        "intent": intent,
        "target": target_name,
        "evidence_paths": evidence_paths,
    }
