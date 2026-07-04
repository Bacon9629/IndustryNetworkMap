# Relationship Types

本文件是 relationship type 的唯一權威清單（taxonomy）。
新增任何 relation type 前，必須先更新本文件，且不得建立語意重複或無語意的邊。

**禁止使用**：`RELATED_TO`、`LINKED_TO`、`ASSOCIATED_WITH`（僅暫時候選資料可例外，且不得進入 verified graph）。

所有關係都有明確方向，graph traversal 與 UI 都必須尊重方向。
關係屬性（confidence / status / period / source_ids 等）見 `docs/development/data-model.md`。

---

## Company → Company

| Type | 語意 | 方向 |
|---|---|---|
| `SUPPLIES_TO` | A 供應產品或服務給 B | 供應方 → 採購方 |
| `MANUFACTURES_FOR` | A 替 B 製造產品（代工） | 製造方 → 委託方 |
| `ASSEMBLES_FOR` | A 替 B 組裝產品 | 組裝方 → 委託方 |
| `COMPETES_WITH` | A 與 B 在相同產品或市場競爭 | 語意對稱，仍只建一條邊 |
| `OWNS` | A 持有或控制 B | 母公司 → 子公司 |
| `INVESTS_IN` | A 投資 B | 投資方 → 被投資方 |
| `BUYS_FROM` | A 從 B 採購 | **避免使用**：優先建 `SUPPLIES_TO`，反向由查詢層推導 |

原則：

- 若 A 供應給 B，建 `A -[:SUPPLIES_TO]-> B`，不要同時建 `B -[:BUYS_FROM]-> A`。
- 同一事實不得建立兩條方向相反、語意重複的邊。
- 供應鏈方向不可顛倒：`台積電 -[:MANUFACTURES_FOR]-> NVIDIA`，不是反過來。

## Company → Product

| Type | 語意 |
|---|---|
| `PRODUCES` | 公司生產某產品 |
| `SELLS` | 公司銷售某產品 |
| `USES` | 公司使用某產品作為投入 |
| `DISTRIBUTES` | 公司代理或通路銷售某產品 |
| `ASSEMBLES` | 公司組裝某產品 |

## Company → Industry

| Type | 語意 |
|---|---|
| `BELONGS_TO` | 公司屬於某產業分類 |

`BELONGS_TO` 也可用於 `Industry → Industry`（子產業 → 母產業）；
`Product/Industry/Application` 的階層另可用 `parent_*_id` 欄位表達，二擇一，MVP 以 `parent_*_id` 為主。

## Product → Product

| Type | 語意 |
|---|---|
| `COMPONENT_OF` | A 是 B 的組件 |
| `INPUT_OF` | A 是 B 的生產投入 |
| `SUBSTITUTE_FOR` | A 可替代 B |
| `USED_WITH` | A 常與 B 搭配使用 |

## Product → Application

| Type | 語意 |
|---|---|
| `USED_IN` | 產品用於某應用 |
| `ENABLES` | 產品使某應用得以實現 |

## Application / Trend → Product

| Type | 語意 |
|---|---|
| `DRIVES_DEMAND_FOR` | 某應用驅動某產品需求 |
| `INCREASES_DEMAND_FOR` | 某趨勢提高某產品需求 |
| `DECREASES_DEMAND_FOR` | 某趨勢降低某產品需求 |

## 任意節點 → Evidence / Source

| Type | 語意 |
|---|---|
| `SUPPORTED_BY` | 節點由某 Evidence 支撐（Evidence 再經 `FROM_SOURCE` 連到 Source） |
| `FROM_SOURCE` | Evidence 來自某 Source |

MVP 階段：關係的來源先以 `source_ids` 屬性記錄即可；
`SUPPORTED_BY` / `FROM_SOURCE` 邊在 Phase 7（審核流程）再全面啟用。

---

## 上游 / 下游定義（供查詢層使用）

以公司 X 為中心：

- **上游**：`(supplier) -[:SUPPLIES_TO|MANUFACTURES_FOR|ASSEMBLES_FOR]-> (X)` 的來源端，
  以及 X `USES` 的產品之生產者。
- **下游**：`(X) -[:SUPPLIES_TO|MANUFACTURES_FOR|ASSEMBLES_FOR]-> (customer)` 的目標端，
  以及 X 產品經 `COMPONENT_OF`/`USED_IN` 到達的產品與應用。

---

## 合法 from/to 型別總表（validator 依此檢查）

| Type | from | to |
|---|---|---|
| SUPPLIES_TO | Company | Company |
| BUYS_FROM | Company | Company |
| MANUFACTURES_FOR | Company | Company |
| ASSEMBLES_FOR | Company | Company |
| COMPETES_WITH | Company | Company |
| OWNS | Company | Company |
| INVESTS_IN | Company | Company |
| PRODUCES | Company | Product |
| SELLS | Company | Product |
| USES | Company | Product |
| DISTRIBUTES | Company | Product |
| ASSEMBLES | Company | Product |
| BELONGS_TO | Company, Industry | Industry |
| COMPONENT_OF | Product | Product |
| INPUT_OF | Product | Product |
| SUBSTITUTE_FOR | Product | Product |
| USED_WITH | Product | Product |
| USED_IN | Product | Application |
| ENABLES | Product | Application |
| DRIVES_DEMAND_FOR | Application | Product |
| INCREASES_DEMAND_FOR | Application | Product |
| DECREASES_DEMAND_FOR | Application | Product |
| SUPPORTED_BY | Company, Product, Industry, Application | Evidence |
| FROM_SOURCE | Evidence | Source |
