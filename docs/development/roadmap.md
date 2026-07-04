# Roadmap（現況版）

完整分階段計畫見 `docs/development/分階段開發計畫.md`。本文件只記錄目前進度與下一步。

## 目前狀態（2026-07-04）

| Phase | 內容 | 狀態 |
|---|---|---|
| 0 | 專案邊界與資料結構定義 | **完成** |
| 1 | Neo4j 基礎建設 | **完成**（docker-compose 啟動、constraints、測試 graph 驗證通過） |
| 2 | Seed data 與匯入流程 | **完成**（MERGE 匯入可重複執行、驗證失敗不匯入） |
| 3 | Backend Graph API（FastAPI） | **完成**（health / search / node / neighborhood / edge，curl 驗證通過） |
| 4 | Frontend Focus Graph（Next.js + Cytoscape.js） | **完成**（搜尋、focus graph、篩選，`npm run build` 通過） |
| 5 | 查詢體驗 | **完成**（節點/邊 Detail Panel、degree、關係摘要、來源） |
| 6 | Demand Shock 分析 | **完成**（API + UI，score = path_confidence × path_decay） |
| 7 | 資料品質與審核流程 | **完成**（Review API + `/review` 頁、created_by/reviewed_* 欄位、docs/development/data-update-rules.md） |
| 8 | 擴充至台股前 100 | **完成**（110 家公司 / 65 產品 / 31 產業 / 16 應用 / 393 關係，已匯入驗證） |
| 9 | RAG / Agent 資料抽取 | **程式完成**（登記/解析/索引/抽取/入庫 candidate；索引與抽取實測待 OPENAI_API_KEY） |
| 10 | 產品化與進階分析 | **完成 10.1-10.3**（key-nodes / bottlenecks / concentration / supply-disruption / demand-shock 方向 / `/api/ask`；10.4 3D 依原則不做） |

## 可運行的系統

```bash
cd infra && docker compose up -d            # Neo4j :7474 / :7687
cd ../ingestion && python scripts/import_graph.py
cd ../backend && python -m uvicorn app.main:app --port 8000
cd ../frontend && npm run dev               # http://localhost:3000
```

頁面：`/` 搜尋、`/node/[id]` Focus Graph、`/demand-shock` 需求變動、`/supply-disruption` 供應中斷、`/analysis` 產業分析、`/ask` 自然語言查詢、`/review` 候選審核。

## RAG pipeline（ingestion/rag/）

```bash
cd ingestion
python rag/register_sources.py     # manifest.csv → Source 節點（不需 key）
python rag/parse_documents.py      # 解析 + chunking → chunks/chunks.jsonl（不需 key）
python rag/build_index.py          # Chroma 向量索引（需 OPENAI_API_KEY）
python rag/search.py "台積電 供應鏈"  # RAG 檢索驗證（需 key）
python rag/extract.py              # LLM 抽取 candidate entities/relationships（需 key）
python rag/load_candidates.py      # 寫入 Neo4j，一律 status=candidate → /review 審核（不需 key）
```

## 待辦

1. 待 OPENAI_API_KEY：RAG 索引 / 檢索 / 抽取與 `/api/ask` 端對端實測。
2. 進階 shock 因子（原物料價格 / 地緣 / 匯率 / 利率）需外部數據源，暫不實作。

## 明確的「還不做」

- 不做爬蟲；文件由人工放入 `ingestion/rag/documents/` 並登記 manifest。
- LLM 產出只進 candidate，不直寫 verified graph（經 `/review` 人工審核）。
- 不做 3D graph；Focus Graph 不顯示全圖。
