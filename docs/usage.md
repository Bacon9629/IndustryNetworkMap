# 操作與使用說明

台股產業鏈知識圖譜 Web App 的安裝、啟動與各功能操作指南。

## 1. 環境需求

- Docker（跑 Neo4j）
- Python 3.12+
- Node.js 18+
- OpenAI API key（僅自然語言查詢與 RAG 抽取需要，其餘功能不需要）

## 2. 安裝與啟動

### 2.1 啟動 Neo4j

```bash
cd infra
docker compose up -d
```

- Neo4j Browser：http://localhost:7474（帳密 `neo4j` / `industrymap_dev`）
- Bolt：`bolt://localhost:7687`

### 2.2 匯入 seed graph

```bash
cd ingestion
pip install -r requirements.txt
python scripts/import_graph.py          # 驗證 + 匯入（可重複執行）
python scripts/import_graph.py --wipe   # 清空後重建
```

匯入前會自動驗證 seed CSV，任何錯誤會列出檔案與 row 並中止，不會寫入。

### 2.3 啟動 Backend（:8000）

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

API 文件（Swagger UI）：http://localhost:8000/docs

### 2.4 啟動 Frontend（:3000）

```bash
cd frontend
npm install
npm run dev
```

### 2.5 設定 OpenAI API Key（選用）

在 repo 根目錄建立 `.env`：

```text
OPENAI_API_KEY=sk-...
```

Backend 與 ingestion script 會自動讀取。可另設 `OPENAI_MODEL`（預設 `gpt-4o-mini`）、
`OPENAI_EMBEDDING_MODEL`（預設 `text-embedding-3-small`）。
未設定時 `/api/ask` 回 503，RAG 索引與抽取 script 會提示缺 key，其餘功能不受影響。

## 3. 各頁面操作

| 頁面 | 路徑 | 功能 |
|---|---|---|
| 搜尋 | `/` | 以中文名 / 英文名 / 股票代號 / 別名搜尋公司、產品、產業、應用 |
| Focus Graph | `/node/[id]` | 以某節點為中心的局部圖 |
| Demand Shock | `/demand-shock` | 需求增加（誰受益）/ 需求下降（誰受害）分析 |
| 供應中斷 | `/supply-disruption` | 某公司或產品斷供時的下游影響分析 |
| 產業分析 | `/analysis` | 關鍵節點 / 供應鏈瓶頸 / 供應商與客戶集中度 |
| 提問 | `/ask` | 自然語言查詢（需 OPENAI_API_KEY） |
| 審核 | `/review` | 審核 candidate 關係 |

### 3.1 搜尋與 Focus Graph

1. 在首頁輸入關鍵字（例：`台積電`、`2330`、`AI Server`），點選結果進入節點頁。
2. 節點頁左側是 graph，右側是 Detail Panel：
   - **深度**：1-3 hop（不提供全圖，避免圖過大）。
   - **方向**：上游（入邊）/ 下游（出邊）/ 雙向。
   - **關係類型 / 最低 confidence / status** 篩選。
   - 實線 = verified，虛線 = candidate（未審核）。
3. 點節點看屬性與關係摘要；點邊看關係語意、confidence、來源與 evidence。

### 3.2 Demand Shock 分析

1. 搜尋並選擇目標（Product 或 Application，例：AI Server）。
2. 選方向：需求增加（受益）或需求下降（受害）、傳導深度 1-4、是否只看台股。
3. 結果列出受影響公司、score 與傳導路徑。
   score = 路徑 confidence 乘積 × 深度衰減（1-hop 1.0 / 2-hop 0.7 / 3-hop 0.5 / 4-hop 0.3）。

### 3.3 供應中斷分析

選擇目標公司或產品後，列出下游受影響公司；`has_alternative` 表示該路徑上的
產品有替代品或多家生產者，中斷衝擊可能較低。

### 3.4 產業分析

- **關鍵節點**：依連結數（degree）排行，可篩選節點類型。
- **瓶頸**：生產者數量 ≤ N 的產品與其少數生產者。
- **集中度**：輸入公司，看上游供應商 / 下游客戶的加權占比
  （以關係數 × confidence 計算；無營收占比資料，`revenue_share` 標 unknown）。

### 3.5 自然語言查詢

輸入中文問題，例：

> 如果 AI Server 需求增加，台股有哪些公司可能受益？

系統流程：LLM 解析意圖 → 執行對應 graph 分析 → 生成解釋（只引用實際存在的
路徑與 confidence，candidate 關係會註明「未經審核」）。支援：需求增減、
供應中斷、瓶頸、關鍵節點。

### 3.6 審核 candidate 關係

`/review` 頁列出所有 `status=candidate` 的關係（含來源與 evidence）：

- **接受** → 轉為 verified，記錄審核時間。
- **修改** → 調整 confidence / 備註後再接受。
- **拒絕** → 轉為 rejected（所有查詢一律排除，不會刪除）。

## 4. RAG / LLM 資料抽取

從文件半自動抽取供應鏈關係，產出一律是 candidate，需經 `/review` 人工審核。

1. 把文件（txt / HTML / PDF）放入 `ingestion/rag/documents/`，
   並在 `manifest.csv` 登記（file, source_id, company_id, period, type, url, title, language）。
2. 依序執行（於 `ingestion/`）：

```bash
python rag/register_sources.py     # 登記 Source 節點（不需 key）
python rag/parse_documents.py      # 解析 + chunking（不需 key）
python rag/build_index.py          # 建 Chroma 向量索引（需 key）
python rag/search.py "查詢文字"     # 檢索驗證（需 key）
python rag/extract.py              # LLM 抽取關係（需 key）
python rag/load_candidates.py      # 寫入 Neo4j candidate（不需 key）
```

3. 到 `/review` 頁審核。無法對應既有節點的抽取結果會輸出到
   `rag/extracted/unresolved_entities.jsonl`，需人工建節點後重跑。

## 5. 新增 / 修改 seed data

1. 編輯 `ingestion/seeds/*.csv`（欄位定義見 `docs/development/data-model.md`）。
2. 關係必附 `confidence`、`status`、`source_ids`；relationship type 必須在
   `docs/development/relationship-types.md` 白名單內。
3. 執行 `python validators/validate.py` 驗證，再 `python scripts/import_graph.py` 匯入。

## 6. 常見問題

- **`/api/ask` 回 503**：未設定 `OPENAI_API_KEY`，見 2.5。
- **OpenAI 回 429 insufficient_quota**：API 帳戶額度不足，到 OpenAI billing 頁確認。
- **匯入報錯**：訊息會指出檔案與 row；修正後重跑即可（MERGE-based，不會產生重複）。
- **改了 seed 但頁面沒變**：重新執行 `import_graph.py`；瀏覽器重新整理。
