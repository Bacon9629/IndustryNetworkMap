"use client";

import Link from "next/link";
import { useState } from "react";
import { api, SearchResult } from "@/lib/api";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function doSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q.trim())}`);
      setResults(data.results);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>搜尋公司 / 產品 / 產業 / 應用</h1>
      <form onSubmit={doSearch}>
        <input
          className="search-box"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="例如：台積電、2330、AI Server、散熱"
          autoFocus
        />
      </form>
      {loading && <p className="muted">搜尋中…</p>}
      {error && <p className="error">{error}</p>}
      {results && results.length === 0 && <p className="muted">沒有結果。</p>}
      {results && results.length > 0 && (
        <ul className="result-list">
          {results.map((r) => (
            <li key={r.id}>
              <Link href={`/node/${encodeURIComponent(r.id)}`}>
                <span className={`badge ${r.type}`}>{r.type}</span>
                <strong>{r.name}</strong>
                {r.ticker && <span className="muted">{r.ticker} · {r.exchange}</span>}
                {r.description && <span className="muted">{r.description}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
