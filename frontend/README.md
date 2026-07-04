# Frontend（Next.js + TypeScript + Cytoscape.js）

## 啟動

```bash
npm install
npm run dev   # http://localhost:3000（需 backend 於 :8000）
```

Backend 位址可用 `NEXT_PUBLIC_API_URL` 覆寫，預設 `http://localhost:8000`。

## 頁面

| 路徑 | 功能 |
|---|---|
| `/` | 搜尋公司 / 產品 / 產業 / 應用 |
| `/node/[id]` | Focus Graph：深度(1-3)、上游/下游、關係類型群組、confidence、status 篩選；點節點/邊顯示右側 Detail Panel |
| `/demand-shock` | 需求衝擊分析：選 Product/Application 目標，顯示受益公司、score、傳導路徑 |

## 原則

- Focus Graph 不顯示全圖（中心節點 + 深度 + 篩選）。
- 實線 = verified、虛線 = candidate；節點色：藍公司 / 綠產品 / 橘產業 / 紅應用。
- 2D only，不做 3D。
