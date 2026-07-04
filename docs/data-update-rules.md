# 資料更新規則（Phase 7.3）

目的：資料更新不破壞歷史紀錄，同一關係可追蹤時間變化。

## Status 生命週期

```text
candidate ──接受──→ verified ──失效──→ stale / deprecated
    │
    └──拒絕──→ rejected（保留於 graph，所有查詢排除）
```

| 狀態 | 何時使用 | 查詢行為 |
|---|---|---|
| candidate | 新建立、未經人工審核（含所有 LLM 抽取結果） | 顯示（虛線），分析可用 confidence 過濾 |
| verified | 人工審核接受，或 seed 中公開周知事實 | 正常顯示與分析 |
| rejected | 審核拒絕 | 一律排除 |
| stale | 超過 period_end 且無新來源確認仍有效 | 顯示但應標注過期，分析建議排除 |
| deprecated | 結構性失效（關係已確定不存在，如客戶轉單、公司併購消滅） | 一律排除 |

## 更新規則

1. **新期間 = 新關係**：同一 from/to/type 在新期間再次確認 → 建立新 rel id（新 period_start/period_end、新 source），舊關係不刪除。
2. **標記 stale**：`period_end` 已過且 12 個月內無新來源再確認 → 人工或批次腳本標 `status=stale`。
3. **標記 deprecated**：有來源明確指出關係已不存在 → 標 `status=deprecated` 並在 `review_note` 記錄依據來源；不刪除。
4. **同期間內可直接覆蓋的情況**：同一關係在同一 period 內取得更好來源 → 直接更新 `confidence` / `source_ids` / `value_type`（`updated_at` 記錄時間）；語意不變才可覆蓋，語意改變（type / from / to）必須 reject + 新建。
5. **審核欄位**：狀態轉換一律寫入 `reviewed_at` / `reviewed_by` / `review_note`（Review API 自動處理）。
6. **禁止硬刪除**：正式 graph 中的關係只改 status，不 DELETE；唯一例外是 `import_graph.py --wipe` 全量重建（seed 是 single source of truth）。

## 關係審核欄位（Phase 7.1）

| 欄位 | 說明 |
|---|---|
| created_by | `manual_seed` 或 `llm_extraction` |
| reviewed_at / reviewed_by | 最近一次審核動作 |
| review_note | 審核備註（接受/拒絕理由、deprecated 依據） |

Review API 見 backend/README.md；審核 UI 為 frontend `/review`。
