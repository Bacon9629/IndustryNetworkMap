# Backend（FastAPI）

Graph query API，資料來源為 Neo4j。

## 啟動

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

連線設定用環境變數 `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` 覆寫（預設對應 infra/docker-compose.yml）。

## API

| Method | Path | 說明 |
|---|---|---|
| GET | `/health` | 服務與 Neo4j 連線狀態 |
| GET | `/api/search?q=` | 搜尋公司/產品/產業/應用（名稱、英文名、代號、別名） |
| GET | `/api/nodes/{node_id}` | 節點詳情 + degree + 關係摘要 |
| GET | `/api/graph/neighborhood` | 局部圖：`node_id`, `depth`(1-3), `direction`(upstream/downstream/both), `relationship_types`, `min_confidence`, `status` |
| GET | `/api/edges/{edge_id}` | 關係詳情 + sources + evidence |
| POST | `/api/analysis/demand-shock` | 需求變動分析：`target_node_id`, `depth`(1-4), `min_confidence`, `tw_only`, `limit`, `shock_direction`(increase/decrease) |
| POST | `/api/analysis/supply-disruption` | 供應中斷分析：同上參數，回傳受影響公司含 `has_alternative` |
| GET | `/api/analysis/key-nodes` | degree 中心性排行：`node_type`, `limit` |
| GET | `/api/analysis/bottlenecks` | 供應鏈瓶頸（生產者 ≤ `max_producers` 的產品） |
| GET | `/api/analysis/concentration?company_id=` | 上游供應商 / 下游客戶集中度（confidence 加權關係數） |
| GET | `/api/review/candidates` | 列出 status=candidate 關係（篩選 rel_type / min_confidence / created_by，分頁） |
| POST | `/api/review/candidates/{edge_id}/accept` | 接受 → verified，寫 reviewed_at / review_note |
| POST | `/api/review/candidates/{edge_id}/reject` | 拒絕 → rejected |
| PATCH | `/api/review/candidates/{edge_id}` | 修改 confidence / note / period（不可改 type 與端點） |
| GET | `/api/review/nodes` | 列出 status=candidate 節點（篩選 label / min_confidence / created_by，分頁） |
| POST | `/api/review/nodes/{node_id}/accept` | 接受 → verified，寫 reviewed_at / review_note |
| POST | `/api/review/nodes/{node_id}/reject` | 拒絕 → rejected（保留於 graph，搜尋/圖譜預設排除） |
| PATCH | `/api/review/nodes/{node_id}` | 修改 name / aliases / description / category / confidence / review_note（不可改 id） |
| POST | `/api/ask` | 自然語言查詢：LLM 解析 intent → 執行分析 → 生成解釋（需 `OPENAI_API_KEY`，未設定回 503） |

## 設計備註

- upstream = 入邊、downstream = 出邊（邊方向慣例見 `docs/development/relationship-types.md`）。
- relationship type 白名單在 `app/config.py`，必須與 `docs/development/relationship-types.md` 同步。
- demand shock score = path_confidence × path_decay（1-hop 1.0 / 2-hop 0.7 / 3-hop 0.5 / 4-hop 0.3）；
  exposure / demand_relevance 尚無資料，回傳 `unknown` 不假造。
- `status: rejected` 的關係一律排除。
- concentration 以關係數 × confidence 加權計算占比；無營收占比資料 → `revenue_share: unknown`。
- `/api/ask` 的 LLM 回答被 prompt 限制只能引用實際分析結果；candidate 關係須註明「未經審核」。
- LLM 模型用環境變數 `OPENAI_MODEL` 設定（預設 gpt-4o-mini）。
