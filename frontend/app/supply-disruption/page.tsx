"use client";

import Link from "next/link";
import { useState } from "react";
import { api, SearchResult, SupplyDisruptionResponse } from "@/lib/api";

export default function SupplyDisruptionPage() {
  const [q, setQ] = useState("");
  const [candidates, setCandidates] = useState<SearchResult[]>([]);
  const [target, setTarget] = useState<SearchResult | null>(null);
  const [depth, setDepth] = useState(2);
  const [twOnly, setTwOnly] = useState(true);
  const [result, setResult] = useState<SupplyDisruptionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function searchTargets(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    const data = await api<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q.trim())}`);
    setCandidates(data.results.filter((r) => r.type === "Company" || r.type === "Product"));
  }

  async function run() {
    if (!target) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api<SupplyDisruptionResponse>("/api/analysis/supply-disruption", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_node_id: target.id, depth, tw_only: twOnly }),
      });
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const maxScore = result?.affected_companies[0]?.score ?? 1;

  return (
    <div>
      <h1>供應中斷分析：若供給中斷，誰受影響？</h1>

      <form onSubmit={searchTargets}>
        <input
          className="search-box"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="搜尋中斷來源（公司或產品），例如：台光電、ABF 載板"
        />
      </form>

      {candidates.length > 0 && !target && (
        <ul className="result-list">
          {candidates.map((c) => (
            <li key={c.id}>
              <a href="#" onClick={(e) => { e.preventDefault(); setTarget(c); }}>
                <span className={`badge ${c.type}`}>{c.type}</span>
                <strong>{c.name}</strong>
                <span className="muted">{c.description}</span>
              </a>
            </li>
          ))}
        </ul>
      )}

      {target && (
        <div className="controls">
          <span>
            中斷目標：<span className={`badge ${target.type}`}>{target.type}</span> <strong>{target.name}</strong>
          </span>
          <label>
            深度
            <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
            </select>
          </label>
          <label>
            <input type="checkbox" checked={twOnly} onChange={(e) => setTwOnly(e.target.checked)} />
            只看台股
          </label>
          <button className="primary" onClick={run} disabled={loading}>
            {loading ? "分析中…" : "執行分析"}
          </button>
          <button onClick={() => { setTarget(null); setResult(null); }}>重選目標</button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <>
          <h2>可能受影響公司（{result.affected_companies.length}）</h2>
          <table className="shock-table">
            <thead>
              <tr>
                <th>公司</th>
                <th>代號</th>
                <th style={{ width: 180 }}>Impact Score</th>
                <th>替代來源</th>
                <th>傳導路徑（最佳）</th>
              </tr>
            </thead>
            <tbody>
              {result.affected_companies.map((c) => (
                <tr key={c.company_id}>
                  <td><Link href={`/node/${encodeURIComponent(c.company_id)}`}>{c.name}</Link></td>
                  <td>{c.ticker}</td>
                  <td>
                    <div className="score-bar" style={{ width: `${(c.score / maxScore) * 160}px` }} />
                    <span className="muted">{c.score}</span>
                  </td>
                  <td>{c.has_alternative ? "有（替代品或多供應商）" : "未知 / 無"}</td>
                  <td className="path-chain">
                    {c.path.nodes.map((n, i) => (
                      <span key={i}>
                        {i > 0 && ` →(${c.path.edges[i - 1]?.type}) `}
                        {n.name}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">
            score = path_confidence × path_decay。替代來源依 SUBSTITUTE_FOR 或其他生產者判斷，僅反映 graph 覆蓋範圍。
          </p>
        </>
      )}
    </div>
  );
}
