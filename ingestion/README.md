# Ingestion

Seed data 與 Neo4j 匯入流程。Graph 必須能由本目錄的 seed 完整重建。

## 結構

```text
seeds/       seed CSV + universe_tw_top100.csv（格式定義見 docs/development/data-model.md、docs/development/relationship-types.md）
validators/  匯入前驗證（id 唯一、from/to 存在、type 合法、confidence/status 合法…）
scripts/     import_graph.py — MERGE-based 匯入，可重複執行
rag/         RAG / LLM 抽取 pipeline（文件登記 → 解析 → 索引 → 抽取 → candidate 入庫）
```

## 使用方式

```bash
# 1. 啟動 Neo4j（見 infra/）
cd ../infra && docker compose up -d

# 2. 安裝依賴
cd ../ingestion && pip install -r requirements.txt

# 3. 只驗證
python validators/validate.py

# 4. 驗證 + 匯入（重複執行安全；--wipe 可清空重建）
python scripts/import_graph.py
python scripts/import_graph.py --wipe
```

連線設定可用環境變數 `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` 覆寫，
預設 `bolt://localhost:7687`, `neo4j` / `industrymap_dev`（與 infra/docker-compose.yml 一致）。

## Seed 資料規則

- 每條關係必附 `confidence`、`status`、`source_ids`。
- 沒有來源的數值標 `value_type: unknown`，不得編造。
- 禁止 `RELATED_TO` 等模糊關係；新 type 需先更新 `docs/development/relationship-types.md`。
- `aliases` / `source_ids` 以 `;` 分隔。
- 驗證失敗會列出檔案與 row，且完全不寫入。

## RAG pipeline（rag/）

不做爬蟲：文件由人工放入 `rag/documents/` 並在 `manifest.csv` 登記（file, source_id, company_id, period, type, url, title, language）。

```bash
python rag/register_sources.py     # manifest → MERGE Source 節點（不需 key）
python rag/parse_documents.py      # txt/HTML/PDF 解析 + chunking → rag/chunks/chunks.jsonl（不需 key）
python rag/build_index.py          # Chroma 向量索引（需 OPENAI_API_KEY）
python rag/search.py "查詢文字"     # RAG 檢索驗證（需 key）
python rag/extract.py              # LLM structured output 抽取 entities/relationships（需 key）
python rag/load_candidates.py      # 寫入 Neo4j，一律 status=candidate（不需 key）
```

鐵律：LLM 抽取結果一律 `status=candidate`、`created_by=llm_extraction`、`value_type=inferred`，
須經前端 `/review` 頁人工審核才會變 verified；relationship type 重用 validator 白名單，
對不上既有節點的實體輸出到 `rag/unresolved_entities.jsonl`，不直接入庫。

環境變數：`OPENAI_API_KEY`（必要）、`OPENAI_MODEL`（預設 gpt-4o-mini）、`OPENAI_EMBEDDING_MODEL`（預設 text-embedding-3-small）。
