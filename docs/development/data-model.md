# Data Model

本文件定義正式 graph（Neo4j）中所有節點類型的欄位、命名規則與 id 規則。
本文件是 schema 的唯一權威來源；seed CSV、validator、import script 都必須與本文件對齊。

來源設計文件：`docs/development/台股產業鏈知識圖譜_WebApp_專案設計文件.md` 第 10、12、13 章。

---

## 通用規則

所有節點與關係都必須具備：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | string | 唯一主鍵，見各節點 id 規則 |
| `created_at` | ISO 8601 datetime | 由 import script 於首次建立時寫入 |
| `updated_at` | ISO 8601 datetime | 每次更新時由 import script 寫入 |

其他通用原則：

- 允許 `unknown`，不允許假精確。沒有來源的數值一律標 `value_type: unknown`。
- 同一實體只能有一個節點；別名放 `aliases`，不建立重複節點。
- `aliases` 在 CSV 中以分號 `;` 分隔。

---

## 節點類型

### Company

代表公司，含台股與海外公司。

**id 規則**：`{EXCHANGE}_{TICKER}`，全大寫。
- 台股上市：`TWSE_2330`
- 台股上櫃：`TPEX_3105`
- 海外公司：`{主要交易所或國別}_{TICKER}`，例如 `US_NVDA`、`US_AAPL`、`KR_005930`（Samsung）、`NL_ASML`

**必要欄位**：`id`, `name`, `ticker`, `exchange`, `country`, `is_listed_in_tw`, `created_at`, `updated_at`

**建議欄位**：`english_name`, `aliases`, `market`, `industry_code`, `website`, `description`, `snapshot_date`, `market_cap_rank_snapshot`

範例：

```text
Company {
  id: "TWSE_2330",
  name: "台積電",
  english_name: "Taiwan Semiconductor Manufacturing Company",
  ticker: "2330",
  exchange: "TWSE",
  country: "Taiwan",
  is_listed_in_tw: true
}
```

海外公司允許進入 graph，標記 `is_listed_in_tw: false`。

### Product

代表產品、服務或零組件。

**id 規則**：小寫 snake_case 英文語意名，例如 `ai_server`, `ai_gpu`, `hbm`, `cowos`, `power_supply`。

**必要欄位**：`id`, `name`, `category`, `created_at`, `updated_at`

**建議欄位**：`aliases`, `description`, `unit`, `parent_product_id`

### Industry

代表產業分類。

**id 規則**：小寫 snake_case，例如 `semiconductor_foundry`, `pcb`, `thermal`。

**必要欄位**：`id`, `name`, `created_at`, `updated_at`

**建議欄位**：`parent_industry_id`, `description`

### Application

代表終端應用或需求市場。

**id 規則**：小寫 snake_case，例如 `ai_datacenter`, `electric_vehicle`。

**必要欄位**：`id`, `name`, `created_at`, `updated_at`

**建議欄位**：`description`, `parent_application_id`

### Source

代表資料來源（年報、法說會、新聞、官網等）。

**id 規則**：`source_{語意 slug}`，例如 `source_tsmc_2025_annual_report`。

**必要欄位**：`id`, `title`, `type`, `created_at`, `updated_at`

`type` 允許值：`annual_report`, `financial_report`, `investor_presentation`, `company_website`, `mops`, `exchange_data`, `news`, `research_report`, `manual`

**建議欄位**：`url`, `publisher`, `published_date`, `retrieved_at`, `company_id`, `period`, `language`, `file_path`

### Evidence

代表支撐節點或關係的證據，用於一個關係有多個來源的情況。
（MVP 先定義 schema，Phase 7 才大量使用。）

**id 規則**：`ev_{語意 slug}` 或 `ev_{source_id 去前綴}_{序號}`。

**必要欄位**：`id`, `source_id`, `quote`, `summary`, `confidence`, `created_at`, `updated_at`

**建議欄位**：`page`, `section`, `url`, `extracted_by`, `reviewed_by`, `review_status`

---

## Relationship Properties

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
source_ids      （分號分隔的 source id 清單）
evidence_ids
value
unit
value_type
valid_from
valid_to
last_verified_at
note
```

審核追蹤欄位（Phase 7 起）：

```text
created_by      （manual_seed | llm_extraction）
reviewed_at     （審核時間，ISO 8601）
reviewed_by     （審核者）
review_note     （審核備註）
```

`created_by=llm_extraction` 的關係一律以 `status=candidate` 建立，
經 Review 流程接受後才轉 `verified` 並寫入 `reviewed_at` / `review_note`。

**relationship id 規則**：`rel_{序號或語意 slug}`，例如 `rel_0001` 或
`rel_twse2330_manufactures_for_usnvda`。id 必須全域唯一。

### confidence（0 到 1）

```text
0.90 - 1.00：官方揭露，可信度高
0.70 - 0.89：多來源支持，可信度中高
0.50 - 0.69：單一可靠來源，可信度中
0.30 - 0.49：推論或市場資訊，可信度低
0.00 - 0.29：未確認，不應作為正式分析依據
```

### status

```text
candidate   候選資料，尚未確認
verified    已確認，可用於正式查詢
rejected    已拒絕
stale       資料可能過期，需重新驗證
deprecated  曾經有效，目前不再使用
```

轉換規則：新資料若無充分來源 → `candidate`；經人工確認 → `verified`；
來源矛盾或過期 → `stale`；確認不再成立 → `deprecated`。Agent 產出永遠先是 `candidate`。

### value_type

```text
reported    公司正式揭露
estimated   研究報告或第三方估算
inferred    根據其他資料推論
unknown     目前未知
```

---

## 時間版本

節點與關係支援：`period`, `valid_from`, `valid_to`, `snapshot_date`, `last_verified_at`。

來源互相矛盾時不直接覆蓋，保留多個 evidence，於 review 決定是否標 `stale` 或新增 period-specific relationship。
