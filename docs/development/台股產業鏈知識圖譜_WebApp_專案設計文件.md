# 台股產業鏈知識圖譜 Web App — 專案設計文件

## 1. 文件目的

本文件作為「台股產業鏈知識圖譜 Web App」的專案開發準則，用於定義：

1. 專案目標與邊界。
2. 系統整體架構。
3. 核心資料模型。
4. Graph Database 的設計原則。
5. Web 介面的功能方向。
6. Agent / RAG 在系統中的角色。
7. 資料建立、驗證與更新流程。
8. 分階段開發計畫。

本文件不是最終產品規格書，而是專案初期的「架構與開發基準」。後續實作過程中，若系統需求、資料模型或技術選型有重大變更，應同步更新本文件。

---

## 2. 專案前情提要

本專案的初始想法是建立一個與股票研究相關的公司知識系統。原先曾考慮使用 Markdown 來記錄每一間公司，並透過 Markdown 超連結將公司之間的上下游關係串起來。

經過重新整理後，專案方向調整為：

> 建立一個以 Web 為主要介面的台股產業鏈知識圖譜系統。

系統的核心不是 Markdown，也不是單純的公司資料庫，而是一個以 graph data model 為基礎的投資研究工具。

在這個系統中：

* 公司是節點。
* 產品是節點。
* 產業是節點。
* 原物料、技術、應用市場也可以是節點。
* 公司之間的供應、採購、代工、競爭、持股、通路等關係是邊。
* 每一條邊都應該具有明確語意、時間範圍、可信度與資料來源。
* 使用者可以透過 Web 介面查詢公司、產品或產業，並以 2D / 未來可選 3D 的圖形方式理解產業鏈結構。
* 未來可透過 Agent / RAG 從財報、年報、法說會簡報、新聞與公開資料中半自動建立資料。

---

## 3. 專案核心目標

### 3.1 最終目標

建立一個可查詢、可視覺化、可推理、可追蹤來源的台股產業鏈知識圖譜 Web App。

系統需要能回答以下類型的問題：

* 某家公司有哪些上游供應商？
* 某家公司有哪些下游客戶或應用市場？
* 某家公司主要生產哪些產品？
* 某個產品的供應鏈涉及哪些公司？
* 某個產業需求放大時，哪些台股公司可能受益？
* 某家公司和哪些產業、產品、技術或應用市場有關？
* 某一條公司關係的資料來源是什麼？
* 某一條供應鏈關係的可信度有多高？
* 某家公司是否過度依賴某一產品、客戶、供應商或產業趨勢？

---

### 3.2 初期目標

初期不追求完整覆蓋所有台股，也不追求 Agent 全自動建立資料。

初期目標是：

> 先建立一個架構一致、資料模型穩定、可以手動或半自動匯入資料的產業鏈圖譜 MVP。

MVP 應該能做到：

1. 使用 Neo4j 作為 Graph Database。
2. 建立一批台股公司節點。
3. 建立產品、產業、應用市場節點。
4. 建立公司與公司、公司與產品、產品與應用之間的關係。
5. 透過 Web 介面搜尋公司。
6. 點選公司後顯示其上下游圖。
7. 點選節點或邊後顯示詳細資訊。
8. 支援 1-hop / 2-hop 的局部圖查詢。
9. 支援基本的需求傳導分析，例如「AI Server 需求增加，哪些公司可能受益」。
10. 每個重要節點與關係都能追蹤資料來源與可信度。

---

## 4. 非目標

為了避免專案範圍失控，初期明確不做以下事項：

### 4.1 初期不做完整自動化爬蟲

未來可以做 Agent / RAG，但初期不讓 Agent 直接自動寫入正式資料庫。

初期的資料建立方式應該是：

```text
人工整理 / 半自動匯入
        ↓
資料驗證
        ↓
寫入 Graph Database
```

未來再演進成：

```text
Agent 搜尋資料
        ↓
LLM 抽取候選關係
        ↓
人工審核
        ↓
寫入 Graph Database
```

---

### 4.2 初期不做全市場覆蓋

初期不需要覆蓋所有上市櫃公司。

建議先從：

```text
30 家左右的半導體 / AI Server / 電子供應鏈相關公司
```

開始做出完整流程。

等 schema、API、UI、資料流程穩定後，再擴充到：

```text
台股市值前 100 公司
```

---

### 4.3 初期不追求精確財務估算

很多公司不會明確揭露：

* 某客戶占營收比例。
* 某供應商占採購比例。
* 某零組件占成本比例。
* 某產品占毛利比例。

因此初期允許資料值為：

```text
unknown
estimated
reported
inferred
```

系統應避免為了完整性而填入無根據的數字。

---

### 4.4 初期不以 3D 圖為主

3D graph 可以作為未來探索功能，但 MVP 優先使用 2D graph。

原因：

* 2D 可讀性較高。
* 2D 較適合產業鏈分析。
* 2D 較容易做篩選、標籤與互動。
* 3D 容易變成視覺效果強但分析效率低。

---

## 5. 使用對象

### 5.1 主要使用者

1. 投資研究者。
2. 軟體工程師本人。
3. 對台股產業鏈有研究需求的人。
4. 想理解公司上下游與產業傳導關係的人。

---

### 5.2 使用場景

#### 場景一：查公司上下游

使用者搜尋：

```text
台積電
```

系統顯示：

* 台積電所屬產業。
* 主要產品。
* 上游設備商。
* 上游材料商。
* 下游客戶。
* 下游應用市場。
* 關鍵技術。
* 相關資料來源。

---

#### 場景二：查產品供應鏈

使用者搜尋：

```text
AI Server
```

系統顯示：

* AI Server 的關鍵組件。
* 相關 ODM / EMS 公司。
* 電源供應鏈。
* 散熱供應鏈。
* PCB 供應鏈。
* 連接器供應鏈。
* 晶片與封裝供應鏈。

---

#### 場景三：需求衝擊分析

使用者輸入：

```text
AI Server 需求增加
```

系統透過 graph traversal 找出相關傳導路徑：

```text
AI Server
  → GPU
  → HBM
  → CoWoS
  → PCB
  → 散熱
  → 電源
  → ODM 組裝
```

再映射到可能受益公司。

---

#### 場景四：關係查證

使用者點選某一條關係：

```text
台達電 → AI Server
```

系統顯示：

* 關係類型。
* 供應產品。
* 可信度。
* 時間範圍。
* 資料來源。
* 是否為官方揭露、估算、新聞、研究報告或推論。

---

## 6. 核心設計原則

### 6.1 Graph Database 是核心資料層

系統的核心資料不應儲存在 Markdown，也不應只存在向量資料庫。

Graph Database 是正式的結構化資料來源。

```text
Graph Database = 結構化事實與關係
Vector Database = 文件檢索與證據查找
LLM / Agent = 抽取、整理與解釋輔助
Web UI = 查詢與視覺化互動層
```

---

### 6.2 LLM 不應取代 Graph

LLM 的角色是：

* 幫助抽取資料。
* 幫助產生候選節點。
* 幫助產生候選邊。
* 幫助摘要來源文件。
* 幫助自然語言解釋 graph traversal 結果。

LLM 不應作為正式資料庫，也不應在未審核狀態下直接修改 verified graph。

---

### 6.3 每一條重要關係都應該有來源

Graph 中的關係應盡可能附帶：

* source
* confidence
* period
* status
* last_verified_at

若缺少來源，該關係仍可存在，但應標記為：

```text
status: candidate
confidence: low
```

或：

```text
value_type: unknown
```

---

### 6.4 允許 unknown，不允許假精確

資料模型必須允許 unknown。

例如：

```text
台積電供應 NVIDIA 先進製程代工服務
```

這個關係可能可以確認，但：

```text
NVIDIA 占台積電營收比例
```

不一定有官方揭露。

此時應該記錄：

```text
relationship exists
metric unknown
source available
confidence medium
```

不應任意填入無來源的比例。

---

### 6.5 系統應支援時間版本

產業鏈關係會隨時間改變。

例如：

* 某家公司更換供應商。
* 某產品營收占比上升。
* 某客戶訂單減少。
* 某技術不再是主流。

因此節點與關係應支援：

```text
period
valid_from
valid_to
snapshot_date
last_verified_at
```

---

### 6.6 UI 應採用 Focus Graph，而不是一次顯示全圖

台股前 100 公司加上產品、產業、材料、技術、海外公司後，節點數很容易超過數千個。

因此 Web UI 不應預設顯示全圖。

應採用：

```text
中心節點 + 深度控制 + 篩選器
```

例如：

```text
中心節點：台積電
查詢深度：2
方向：上游 + 下游
關係類型：供應、製造、產品、應用
```

---

## 7. 系統整體架構

### 7.1 初期架構

```text
Frontend Web App
    ↓
Backend API
    ↓
Neo4j Graph Database
```

---

### 7.2 中期架構

```text
Frontend Web App
    ↓
Backend API
    ↓
Neo4j Graph Database
    ↓
Data Import / Validation Scripts
```

---

### 7.3 後期架構

```text
Frontend Web App
    ↓
Backend API
    ├── Graph Query Service
    ├── Demand Shock Service
    ├── Search Service
    └── RAG / Agent Service
            ↓
        Vector Database
            ↓
        Source Documents

Neo4j Graph Database
    ↑
Data Ingestion Pipeline
    ↑
Financial Reports / Annual Reports / Investor Presentations / News
```

---

## 8. 建議技術選型

### 8.1 Frontend

建議：

```text
Next.js + TypeScript
```

理由：

* 適合 Web App。
* TypeScript 有助於資料結構一致性。
* 容易與後端 API 整合。
* 未來可做 SSR、搜尋頁、公司頁、產品頁。

---

### 8.2 Graph Visualization

MVP 建議：

```text
Cytoscape.js
```

理由：

* 適合 network graph。
* 支援節點與邊樣式。
* 支援 layout。
* 支援互動事件。
* 適合 1-hop / 2-hop focus graph。

未來若節點規模變大，可評估：

```text
Sigma.js
```

若未來需要 3D，可評估：

```text
3d-force-graph
```

---

### 8.3 Backend

建議：

```text
FastAPI
```

理由：

* Python 適合資料處理、RAG、LLM pipeline。
* FastAPI 開發 API 快。
* 容易整合 Neo4j driver。
* 後續處理 PDF、財報、爬蟲、向量資料庫較方便。

---

### 8.4 Graph Database

建議：

```text
Neo4j
```

理由：

* 最常見的 graph database。
* Cypher 語法直覺。
* 文件與社群成熟。
* 適合知識圖譜。
* 未來整合 LLM / RAG 工具較方便。

---

### 8.5 未來 RAG / Agent

可後期加入：

```text
LlamaIndex 或 LangChain
Qdrant 或 Chroma
PDF Parser
Crawler
Document Indexer
LLM Extractor
Human Review UI
```

---

## 9. 核心資料邊界

本系統需要明確區分以下資料層：

### 9.1 Formal Graph Data

正式寫入 Neo4j 的資料。

特性：

* 結構化。
* 可查詢。
* 有狀態。
* 有來源。
* 有可信度。
* 是 Web App 的主要資料來源。

---

### 9.2 Candidate Graph Data

由人工、script 或 Agent 產生，但尚未審核的候選資料。

特性：

* 不能直接視為事實。
* 不能直接覆蓋正式資料。
* 需要 review。
* 可被接受、修改、拒絕。

---

### 9.3 Source Documents

原始來源資料。

例如：

* 年報。
* 財報。
* 法說會簡報。
* 公司官網。
* 公開資訊觀測站資料。
* 交易所資料。
* 新聞。
* 研究報告。

Source documents 本身不是 graph，但可以支撐 graph 中的節點與關係。

---

### 9.4 Vector Index

RAG 使用的檢索索引。

特性：

* 用於搜尋來源文件。
* 用於找 evidence。
* 不作為正式事實資料庫。
* 不直接決定 graph 結構。

---

## 10. 初期 Graph Data Model

MVP 先定義以下節點類型。

---

### 10.1 Company

代表公司。

必要欄位：

```text
id
name
ticker
exchange
country
is_listed_in_tw
created_at
updated_at
```

建議欄位：

```text
english_name
aliases
market
industry_code
website
description
snapshot_date
market_cap_rank_snapshot
```

範例：

```text
Company {
  id: "TWSE_2330",
  name: "台積電",
  english_name: "Taiwan Semiconductor Manufacturing Company",
  ticker: "2330",
  exchange: "TWSE",
  country: "Taiwan",
  is_listed_in_tw: true,
  snapshot_date: "2026-07-03"
}
```

---

### 10.2 Product

代表產品、服務或零組件。

必要欄位：

```text
id
name
category
created_at
updated_at
```

建議欄位：

```text
aliases
description
unit
parent_product_id
```

範例：

```text
Product {
  id: "ai_server",
  name: "AI Server",
  category: "Server"
}
```

---

### 10.3 Industry

代表產業分類。

必要欄位：

```text
id
name
created_at
updated_at
```

建議欄位：

```text
parent_industry_id
description
```

範例：

```text
Industry {
  id: "semiconductor_foundry",
  name: "晶圓代工"
}
```

---

### 10.4 Application

代表終端應用或需求市場。

必要欄位：

```text
id
name
created_at
updated_at
```

建議欄位：

```text
description
parent_application_id
```

範例：

```text
Application {
  id: "ai_datacenter",
  name: "AI 資料中心"
}
```

---

### 10.5 Source

代表資料來源。

必要欄位：

```text
id
title
type
created_at
updated_at
```

建議欄位：

```text
url
publisher
published_date
retrieved_at
company_id
period
language
file_path
```

範例：

```text
Source {
  id: "source_tsmc_2025_annual_report",
  title: "台積電 2025 年報",
  type: "annual_report",
  period: "2025"
}
```

---

### 10.6 Evidence

代表支撐某個節點或關係的證據。

Evidence 用於處理一個關係有多個來源的情況。

必要欄位：

```text
id
source_id
quote
summary
confidence
created_at
updated_at
```

建議欄位：

```text
page
section
url
extracted_by
reviewed_by
review_status
```

---

## 11. 初期 Relationship Types

MVP 先使用有限、明確的關係類型。

---

### 11.1 Company → Company

```text
SUPPLIES_TO
BUYS_FROM
MANUFACTURES_FOR
ASSEMBLES_FOR
COMPETES_WITH
OWNS
INVESTS_IN
```

說明：

* `SUPPLIES_TO`：A 供應產品或服務給 B。
* `BUYS_FROM`：A 從 B 採購產品或服務。
* `MANUFACTURES_FOR`：A 替 B 製造產品。
* `ASSEMBLES_FOR`：A 替 B 組裝產品。
* `COMPETES_WITH`：A 與 B 在相同產品或市場競爭。
* `OWNS`：A 持有或控制 B。
* `INVESTS_IN`：A 投資 B。

原則：

* 若 A 供應給 B，優先建立 `A -[:SUPPLIES_TO]-> B`。
* 不必同時建立反向 `B -[:BUYS_FROM]-> A`，反向關係可由查詢層推導。
* 避免同一事實建立兩條方向相反但語意重複的邊。

---

### 11.2 Company → Product

```text
PRODUCES
SELLS
USES
DISTRIBUTES
ASSEMBLES
```

說明：

* `PRODUCES`：公司生產某產品。
* `SELLS`：公司銷售某產品。
* `USES`：公司使用某產品作為投入。
* `DISTRIBUTES`：公司代理或通路銷售某產品。
* `ASSEMBLES`：公司組裝某產品。

---

### 11.3 Product → Product

```text
COMPONENT_OF
INPUT_OF
SUBSTITUTE_FOR
USED_WITH
```

說明：

* `COMPONENT_OF`：A 是 B 的組件。
* `INPUT_OF`：A 是 B 的生產投入。
* `SUBSTITUTE_FOR`：A 可替代 B。
* `USED_WITH`：A 常與 B 搭配使用。

---

### 11.4 Product → Application

```text
USED_IN
ENABLES
```

說明：

* `USED_IN`：產品用於某應用。
* `ENABLES`：產品使某應用得以實現。

---

### 11.5 Application / Trend → Product

```text
DRIVES_DEMAND_FOR
INCREASES_DEMAND_FOR
DECREASES_DEMAND_FOR
```

說明：

* `DRIVES_DEMAND_FOR`：某應用驅動某產品需求。
* `INCREASES_DEMAND_FOR`：某趨勢提高某產品需求。
* `DECREASES_DEMAND_FOR`：某趨勢降低某產品需求。

---

## 12. Relationship Properties

每一條關係至少應有：

```text
id
description
confidence
status
period
created_at
updated_at
```

建議欄位：

```text
product_id
source_ids
evidence_ids
value
unit
value_type
valid_from
valid_to
last_verified_at
note
```

---

### 12.1 confidence

建議使用 0 到 1 的數值。

```text
0.90 - 1.00：官方揭露，可信度高
0.70 - 0.89：多來源支持，可信度中高
0.50 - 0.69：單一可靠來源，可信度中
0.30 - 0.49：推論或市場資訊，可信度低
0.00 - 0.29：未確認，不應作為正式分析依據
```

---

### 12.2 status

關係狀態：

```text
candidate
verified
rejected
stale
deprecated
```

說明：

* `candidate`：候選資料，尚未確認。
* `verified`：已確認，可用於正式查詢。
* `rejected`：已拒絕。
* `stale`：資料可能過期，需要重新驗證。
* `deprecated`：曾經有效，但目前不再使用。

---

### 12.3 value_type

數值來源類型：

```text
reported
estimated
inferred
unknown
```

說明：

* `reported`：公司正式揭露。
* `estimated`：研究報告或第三方估算。
* `inferred`：根據其他資料推論。
* `unknown`：目前未知。

---

## 13. 資料品質規則

### 13.1 公司名稱需要標準化

同一家公司可能有多種名稱：

```text
台積電
TSMC
Taiwan Semiconductor Manufacturing Company
2330
2330.TW
```

系統應使用唯一 `id` 作為主鍵，其他名稱放入 `aliases`。

---

### 13.2 允許外部公司節點

雖然專案以台股為核心，但供應鏈必然包含海外公司。

例如：

* NVIDIA
* Apple
* AMD
* ASML
* Samsung
* SK Hynix
* Applied Materials

這些公司應允許進入 graph。

欄位可標記：

```text
is_listed_in_tw: false
country: "US"
```

---

### 13.3 不同資料來源可能互相矛盾

若來源互相矛盾，不應直接覆蓋資料。

應保留多個 evidence，並在 review 階段決定：

* 哪個來源較可信。
* 是否更新 confidence。
* 是否將舊關係標記為 stale。
* 是否新增新的 period-specific relationship。

---

### 13.4 產業鏈關係需保留方向性

供應鏈關係具有方向。

例如：

```text
台積電 -[:MANUFACTURES_FOR]-> NVIDIA
```

不可混淆為：

```text
NVIDIA -[:MANUFACTURES_FOR]-> 台積電
```

Graph traversal 與 UI 顯示都應尊重方向。

---

## 14. Web App 功能設計

### 14.1 公司搜尋

使用者可搜尋：

* 公司名稱。
* 股票代號。
* 英文名稱。
* 別名。

搜尋結果顯示：

```text
公司名稱
股票代號
交易所
產業
是否為台股公司
```

---

### 14.2 公司頁

公司頁應顯示：

* 基本資料。
* 所屬產業。
* 主要產品。
* 上游關係。
* 下游關係。
* 競爭對手。
* 相關應用市場。
* 關係圖。
* 來源列表。
* 資料最後更新時間。

---

### 14.3 Focus Graph

Focus Graph 是主要視覺化元件。

功能：

* 以指定公司、產品或應用為中心。
* 可調整查詢深度。
* 可切換上游 / 下游 / 全部。
* 可篩選關係類型。
* 可篩選 confidence。
* 可篩選 period。
* 可點擊節點查看詳情。
* 可點擊邊查看詳情。

---

### 14.4 Edge Detail Panel

點選邊時，右側顯示：

```text
關係類型
from node
to node
產品 / 服務
描述
期間
可信度
資料狀態
來源
evidence
last_verified_at
note
```

---

### 14.5 Demand Shock View

使用者輸入一個產品、應用或趨勢，例如：

```text
AI Server demand increase
```

系統執行：

1. 找到對應 Application / Product / MarketTrend 節點。
2. 執行 graph traversal。
3. 找出相關產品。
4. 找出供應該產品的公司。
5. 根據距離、可信度、產品暴露度估算 benefit score。
6. 顯示可能受益公司與傳導路徑。

---

## 15. Demand Shock Scoring 初步設計

初期可以使用簡化模型：

```text
benefit_score =
  relationship_confidence
  × path_decay
  × exposure_score
  × demand_relevance
```

---

### 15.1 relationship_confidence

由 relationship 的 confidence 決定。

---

### 15.2 path_decay

距離越遠，分數越低。

建議：

```text
1-hop: 1.0
2-hop: 0.7
3-hop: 0.5
4-hop: 0.3
```

---

### 15.3 exposure_score

若有營收占比，使用營收占比。

若沒有，初期可用人工標記：

```text
high
medium
low
unknown
```

對應：

```text
high: 1.0
medium: 0.6
low: 0.3
unknown: 0.2
```

---

### 15.4 demand_relevance

產品與需求主題的關聯程度。

例如：

```text
AI Server → GPU: high
AI Server → HBM: high
AI Server → Power Supply: medium-high
AI Server → Connector: medium
AI Server → General Industrial Product: low
```

---

## 16. Backend API 初期需求

### 16.1 Search API

```text
GET /api/search?q={query}
```

用途：

* 搜尋公司、產品、產業、應用。

---

### 16.2 Node Detail API

```text
GET /api/nodes/{node_id}
```

用途：

* 取得節點詳細資料。

---

### 16.3 Neighborhood Graph API

```text
GET /api/graph/neighborhood?node_id={id}&depth={n}&direction={upstream|downstream|both}
```

用途：

* 取得某節點周圍的局部 graph。

---

### 16.4 Edge Detail API

```text
GET /api/edges/{edge_id}
```

用途：

* 取得某條關係的詳細資料與 evidence。

---

### 16.5 Demand Shock API

```text
POST /api/analysis/demand-shock
```

輸入：

```text
target_node_id
shock_type
depth
filters
```

輸出：

```text
affected_companies
paths
scores
explanations
sources
```

---

## 17. 資料建立流程

### 17.1 初期手動 Seed

初期先建立小型但完整的資料集。

建議：

```text
30 家公司
20 個產品
10 個產業
10 個應用
100 條關係
```

---

### 17.2 CSV / JSON 匯入

初期不需要直接做完整後台管理介面。

可先使用：

```text
seed_companies.csv
seed_products.csv
seed_industries.csv
seed_applications.csv
seed_relationships.csv
```

由 import script 匯入 Neo4j。

---

### 17.3 資料驗證

匯入前需驗證：

* relationship 的 from node 是否存在。
* relationship 的 to node 是否存在。
* relationship type 是否合法。
* company id 是否重複。
* product id 是否重複。
* confidence 是否在 0 到 1。
* status 是否為合法 enum。
* source_id 是否存在。
* period 是否存在或允許為 null。
* 是否有孤立節點。
* 是否有方向明顯錯誤的關係。

---

## 18. Agent / RAG 未來定位

Agent / RAG 不屬於 MVP 的第一步，但必須在架構上預留位置。

未來資料 pipeline：

```text
Source Discovery
    ↓
Document Fetching
    ↓
Document Parsing
    ↓
Chunking / Indexing
    ↓
RAG Retrieval
    ↓
Entity Extraction
    ↓
Relationship Extraction
    ↓
Candidate Graph Generation
    ↓
Human Review
    ↓
Neo4j Write
```

---

### 18.1 Agent 不直接寫入 verified graph

Agent 產生的資料預設為：

```text
status: candidate
```

必須經過 review 才能成為：

```text
status: verified
```

---

### 18.2 RAG 負責證據，不負責事實本身

RAG 應用於：

* 找來源。
* 找原文。
* 找 evidence。
* 支撐解釋。
* 幫助審核。

RAG 不應作為正式 graph 的替代品。

---

## 19. 專案目錄建議

初期專案可以採用 monorepo：

```text
stock-industry-graph/
├── docs/
│   ├── design.md
│   ├── data-model.md
│   ├── relationship-types.md
│   └── roadmap.md
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── README.md
│
├── backend/
│   ├── app/
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
├── ingestion/
│   ├── seeds/
│   ├── scripts/
│   ├── validators/
│   └── README.md
│
├── infra/
│   ├── docker-compose.yml
│   └── neo4j/
│
└── README.md
```

---

## 20. 開發優先順序

優先順序應為：

```text
1. 資料模型
2. Graph schema
3. Seed data 格式
4. Neo4j 匯入流程
5. Backend graph query API
6. Frontend focus graph
7. Demand shock traversal
8. 資料驗證與審核流程
9. 台股前 100 擴充
10. Agent / RAG
```

不應該先做大型 UI，再回頭補資料模型。

---

## 21. 成功標準

MVP 成功標準：

1. 可以搜尋公司。
2. 可以顯示公司上下游圖。
3. 可以點擊節點查看公司、產品或產業資訊。
4. 可以點擊邊查看關係意義、來源與可信度。
5. 可以從某個產品或應用找出相關公司。
6. 可以執行簡化版 demand shock 分析。
7. 可以用 seed data 重新建立 Neo4j graph。
8. 資料 schema 穩定，不因新增公司就大幅修改架構。
9. 至少有一個完整產業鏈範例，例如 AI Server / 半導體供應鏈。
10. 後續可以自然擴充到台股前 100。

---

## 22. 主要風險

### 22.1 資料品質風險

供應鏈資料常常不完整、不公開或來自市場傳聞。

解法：

* 使用 confidence。
* 使用 source。
* 使用 status。
* 使用 human review。
* 允許 unknown。

---

### 22.2 Graph 過度複雜

節點過多會導致 UI 不可讀。

解法：

* 使用 Focus Graph。
* 限制 depth。
* 提供 filters。
* 不預設顯示全圖。

---

### 22.3 Relationship type 過度膨脹

如果關係類型太多，資料會難維護。

解法：

* MVP 僅使用有限關係類型。
* 新增 relation type 需先更新 relationship-types 文件。
* 避免建立語意重複的 relation。

---

### 22.4 Agent 產生錯誤資料

LLM 可能抽錯關係、方向、公司名稱或時間。

解法：

* Agent 僅產生 candidate。
* verified graph 需人工審核。
* 每個 extraction 保留 evidence。
* 不允許無來源資料直接進入正式 graph。

---

## 23. 開發準則

### 23.1 資料優先於 UI

若資料模型不清楚，不應優先開發複雜 UI。

---

### 23.2 Graph 是主資料庫

正式關係以 Neo4j 為準。

---

### 23.3 所有重要關係都要能回溯

邊上至少要有：

```text
confidence
status
period
source / evidence
```

---

### 23.4 不建立無語意邊

避免使用：

```text
RELATED_TO
LINKED_TO
ASSOCIATED_WITH
```

除非只是暫時候選資料。

正式 graph 應使用明確 relation type。

---

### 23.5 不為了完整而亂填數字

沒有來源的數值應標記 unknown。

---

### 23.6 不一次顯示全圖

Web UI 預設顯示局部圖。

---

### 23.7 不讓 Agent 直接污染正式資料

Agent output 必須經過 candidate → review → verified 流程。

---

## 24. 初期推薦開發範圍

第一個完整產業鏈建議選：

```text
AI Server / 半導體 / 電源 / 散熱 / PCB / ODM
```

原因：

* 台股相關公司多。
* 產業鏈關係明確。
* 投資研究價值高。
* 需求傳導容易展示。
* 適合做 Demand Shock 範例。

初期公司可包含：

```text
台積電
聯發科
日月光
鴻海
廣達
緯創
英業達
台達電
金像電
健鼎
奇鋐
雙鴻
信邦
貿聯-KY
聯詠
瑞昱
華邦電
南亞科
世界先進
力積電
```

也應允許加入海外節點：

```text
NVIDIA
AMD
Apple
ASML
SK Hynix
Samsung
Micron
```

---

## 25. 結論

本專案應被定義為：

> 台股產業鏈知識圖譜 Web App。

核心架構是：

```text
Neo4j Graph Database
    ↓
FastAPI Backend
    ↓
Next.js Frontend
    ↓
Cytoscape.js Focus Graph
```

未來擴充：

```text
RAG Evidence Retrieval
Agent Candidate Extraction
Human Review
Demand Shock Analysis
```

開發策略應是：

```text
先穩定資料模型
再建立 graph
再建立查詢 API
再建立 Web 視覺化
再擴充台股前 100
最後加入 Agent / RAG 自動化
```

本專案的核心價值不是「列出很多公司」，而是：

> 將公司、產品、產業、技術與需求趨勢之間的關係變成可查詢、可視覺化、可驗證、可推理的結構化知識。
