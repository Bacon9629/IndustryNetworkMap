# Agent 開發規則（AI 協作開發準則）

本文件記錄本專案中 AI（Claude 或其他 LLM agent）參與開發時必須遵守的規則。
規則來源：`台股產業鏈知識圖譜_WebApp_專案設計文件.md`、`分階段開發計畫.md` 與專案負責人指示。

---

## 1. 資料層鐵律

1. **Neo4j 是唯一正式資料層**。Markdown、CSV、向量資料庫都不是主資料庫。
2. Seed CSV 是「匯入來源」，不是資料庫本身；graph 必須能由 seed 完整重建。
3. **LLM / Agent 產出的資料永遠是 `status: candidate`**，未經人工 review 不得寫入 verified graph、不得覆蓋既有 verified 資料。
4. 所有核心節點與關係必須可追蹤：`id`, `type`, `status`, `confidence`, `source / evidence`, `created_at`, `updated_at`。
5. 允許 `unknown`，禁止假精確。沒有來源的數值一律 `value_type: unknown`，不得為了完整性編造數字。

## 2. Schema 鐵律

1. **禁止模糊關係**：不得建立 `RELATED_TO`、`LINKED_TO`、`ASSOCIATED_WITH`。
2. relationship type 必須有明確方向與語意，且必須存在於 `docs/development/relationship-types.md`。
   新增 type 前必須先更新該文件。
3. 同一事實不建兩條方向相反的重複邊（用 `SUPPLIES_TO`，反向由查詢層推導）。
4. 供應鏈方向不可顛倒（`台積電 -[:MANUFACTURES_FOR]-> NVIDIA`）。
5. 同一實體只有一個節點；別名進 `aliases`，id 規則見 `docs/development/data-model.md`。
6. Schema 變更必須先改 `docs/development/data-model.md` / `docs/development/relationship-types.md`，再改 code。

## 3. 開發順序鐵律

1. **資料優先於 UI**：資料模型不穩定前不開發複雜 UI。
2. 先做小型完整流程（~30 家公司），再擴充資料量（前 100 是 Phase 8）。
3. 依 `docs/development/分階段開發計畫.md` 的 phase 順序推進，不跳做 Agent / RAG / 爬蟲 / 3D。
4. UI 一律採 Focus Graph（中心節點 + 深度 + 篩選），不預設顯示全圖。

## 4. 技術選型（不得擅自更換）

| 層 | 選型 |
|---|---|
| Frontend | Next.js + TypeScript |
| Graph 視覺化 | Cytoscape.js（後續 phase 才做） |
| Backend | FastAPI |
| Graph DB | Neo4j |
| Ingestion | Python scripts（CSV → 驗證 → Neo4j） |
| Infra | Docker Compose |

## 5. 匯入與驗證規則

1. 匯入必須可重複執行（MERGE-based），重跑不產生重複節點或關係。
2. 匯入前必須通過 validator：id 唯一、from/to 存在、type 合法（含 from/to 節點型別）、
   confidence ∈ [0,1]、status 合法、source_id 存在、必要欄位非空。
3. 驗證失敗必須指出檔案與 row，且不得部分寫入。
4. 來源互相矛盾時不覆蓋，保留 evidence 待 review。

## 6. AI 協作行為準則

1. 大規模修改前先提出計畫，經確認後執行。
2. 修改 schema、relationship taxonomy、資料流程時，必須同步更新 docs/ 對應文件。
3. 不建立與文件矛盾的資料或程式；發現文件間矛盾時，先提出而非自行裁決。
4. 產出 seed data 時，每條關係必須附 `source_ids` 與 `confidence`；
   由 AI 推論而非來源明載的關係，`status` 一律 `candidate`、`value_type` 一律 `inferred`。
5. 不做超出當前 phase 的實作（例如在 Phase 2 就寫前端元件）。

## 7. 文件目錄約定

- `doc/`：原始設計文件（設計文件、分階段計畫）與本規則文件。人工維護為主。
- `docs/`：開發過程的權威工作文件（data-model、relationship-types、roadmap）。
  schema 與 taxonomy 以 `docs/` 為準；`doc/` 為背景與初始依據。
