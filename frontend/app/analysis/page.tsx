"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  api, Bottleneck, ConcentrationEntry, ConcentrationResponse, KeyNode, SearchResult,
} from "@/lib/api";

type Tab = "key-nodes" | "bottlenecks" | "concentration";

export default function AnalysisPage() {
  const [tab, setTab] = useState<Tab>("key-nodes");
  const [error, setError] = useState<string | null>(null);

  const [nodeType, setNodeType] = useState("");
  const [keyNodes, setKeyNodes] = useState<KeyNode[]>([]);

  const [maxProducers, setMaxProducers] = useState(2);
  const [bottlenecks, setBottlenecks] = useState<Bottleneck[]>([]);

  const [q, setQ] = useState("");
  const [candidates, setCandidates] = useState<SearchResult[]>([]);
  const [conc, setConc] = useState<ConcentrationResponse | null>(null);

  const loadKeyNodes = useCallback(async () => {
    const qs = new URLSearchParams({ limit: "30" });
    if (nodeType) qs.set("node_type", nodeType);
    try {
      const data = await api<{ nodes: KeyNode[] }>(`/api/analysis/key-nodes?${qs}`);
      setKeyNodes(data.nodes);
      setError(null);
    } catch (err) { setError(String(err)); }
  }, [nodeType]);

  const loadBottlenecks = useCallback(async () => {
    try {
      const data = await api<{ bottlenecks: Bottleneck[] }>(`/api/analysis/bottlenecks?max_producers=${maxProducers}&limit=50`);
      setBottlenecks(data.bottlenecks);
      setError(null);
    } catch (err) { setError(String(err)); }
  }, [maxProducers]);

  useEffect(() => {
    if (tab === "key-nodes") loadKeyNodes();
    if (tab === "bottlenecks") loadBottlenecks();
  }, [tab, loadKeyNodes, loadBottlenecks]);

  async function searchCompany(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    const data = await api<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q.trim())}`);
    setCandidates(data.results.filter((r) => r.type === "Company"));
  }

  async function loadConcentration(id: string) {
    try {
      setConc(await api<ConcentrationResponse>(`/api/analysis/concentration?company_id=${encodeURIComponent(id)}`));
      setCandidates([]);
      setError(null);
    } catch (err) { setError(String(err)); }
  }

  function ConcTable({ title, rows }: { title: string; rows: ConcentrationEntry[] }) {
    return (
      <>
        <h3>{title}（{rows.length}）</h3>
        <table className="shock-table">
          <thead>
            <tr><th>公司</th><th>代號</th><th>關係數</th><th>加權比重</th><th>關係</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.company_id}>
                <td><Link href={`/node/${encodeURIComponent(r.company_id)}`}>{r.name}</Link></td>
                <td>{r.ticker}</td>
                <td>{r.edge_count}</td>
                <td>{(r.share * 100).toFixed(1)}%</td>
                <td className="muted">
                  {r.edges.map((e, i) => (
                    <span key={i}>{i > 0 && "、"}{e.type}{e.product_id ? `（${e.product_id}）` : ""}</span>
                  ))}
                </td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={5} className="muted">graph 中無資料</td></tr>}
          </tbody>
        </table>
      </>
    );
  }

  return (
    <div>
      <h1>產業分析</h1>

      <div className="controls">
        <button className={tab === "key-nodes" ? "primary" : ""} onClick={() => setTab("key-nodes")}>關鍵節點</button>
        <button className={tab === "bottlenecks" ? "primary" : ""} onClick={() => setTab("bottlenecks")}>供應鏈瓶頸</button>
        <button className={tab === "concentration" ? "primary" : ""} onClick={() => setTab("concentration")}>集中度</button>
      </div>

      {error && <p className="error">{error}</p>}

      {tab === "key-nodes" && (
        <>
          <div className="controls">
            <label>
              節點類型
              <select value={nodeType} onChange={(e) => setNodeType(e.target.value)}>
                <option value="">全部</option>
                <option value="Company">Company</option>
                <option value="Product">Product</option>
                <option value="Industry">Industry</option>
                <option value="Application">Application</option>
              </select>
            </label>
          </div>
          <table className="shock-table">
            <thead>
              <tr><th>節點</th><th>類型</th><th>總 degree</th><th>入</th><th>出</th></tr>
            </thead>
            <tbody>
              {keyNodes.map((n) => (
                <tr key={n.id}>
                  <td><Link href={`/node/${encodeURIComponent(n.id)}`}>{n.name}</Link>{n.ticker ? <span className="muted">（{n.ticker}）</span> : null}</td>
                  <td><span className={`badge ${n.type}`}>{n.type}</span></td>
                  <td>{n.total_degree}</td>
                  <td>{n.in_degree}</td>
                  <td>{n.out_degree}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">依 degree 中心性排序（排除 rejected 關係）。</p>
        </>
      )}

      {tab === "bottlenecks" && (
        <>
          <div className="controls">
            <label>
              生產者 ≤
              <select value={maxProducers} onChange={(e) => setMaxProducers(Number(e.target.value))}>
                {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
          </div>
          <table className="shock-table">
            <thead>
              <tr><th>產品</th><th>生產者數</th><th>生產者</th><th>下游使用數</th></tr>
            </thead>
            <tbody>
              {bottlenecks.map((b) => (
                <tr key={b.product_id}>
                  <td><Link href={`/node/${encodeURIComponent(b.product_id)}`}>{b.name}</Link></td>
                  <td>{b.producer_count}</td>
                  <td>
                    {b.producers.map((p, i) => (
                      <span key={p.id}>{i > 0 && "、"}<Link href={`/node/${encodeURIComponent(p.id)}`}>{p.name}</Link></span>
                    ))}
                  </td>
                  <td>{b.downstream_usage}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">graph 中 PRODUCES 生產者少的產品，代表潛在供應鏈瓶頸（僅反映 graph 覆蓋範圍）。</p>
        </>
      )}

      {tab === "concentration" && (
        <>
          <form onSubmit={searchCompany}>
            <input
              className="search-box" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="搜尋公司，例如：台積電、2330"
            />
          </form>
          {candidates.length > 0 && (
            <ul className="result-list">
              {candidates.map((c) => (
                <li key={c.id}>
                  <a href="#" onClick={(e) => { e.preventDefault(); loadConcentration(c.id); }}>
                    <strong>{c.name}</strong> <span className="muted">{c.ticker}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
          {conc && (
            <>
              <h2>{conc.company.name} 供應鏈集中度</h2>
              <p className="muted">
                計算基礎：{conc.basis}（關係數 × confidence 加權）；實際營收占比：{conc.revenue_share}。
              </p>
              <ConcTable title="上游供應商" rows={conc.suppliers} />
              <ConcTable title="下游客戶" rows={conc.customers} />
            </>
          )}
        </>
      )}
    </div>
  );
}
