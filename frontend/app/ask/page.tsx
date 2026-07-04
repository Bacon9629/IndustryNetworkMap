"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";

interface AskResponse {
  answer: string;
  intent: string;
  target?: string | null;
  evidence_paths: {
    nodes: { id: string; name: string; type: string }[];
    edges: { id: string; type: string; confidence: number | null; status?: string | null }[];
  }[];
}

const EXAMPLES = [
  "如果 AI Server 需求增加，台股有哪些公司可能受益？",
  "台光電如果供貨中斷，會影響哪些公司？",
  "目前產業鏈中有哪些供應鏈瓶頸？",
];

export default function AskPage() {
  const [q, setQ] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await api<AskResponse>("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q.trim() }),
      });
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>自然語言查詢</h1>
      <p className="muted">用中文提問，系統解析後執行 graph 分析並生成解釋（需後端設定 OPENAI_API_KEY）。</p>

      <form onSubmit={submit}>
        <input
          className="search-box"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="例如：如果 AI Server 需求增加，台股有哪些公司可能受益？"
        />
        <button className="primary" type="submit" disabled={loading} style={{ marginTop: 8 }}>
          {loading ? "分析中…" : "提問"}
        </button>
      </form>

      <div className="controls" style={{ marginTop: 8 }}>
        {EXAMPLES.map((ex) => (
          <button key={ex} onClick={() => setQ(ex)}>{ex}</button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <>
          <h2>回答 <span className="muted">（intent: {result.intent}）</span></h2>
          <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{result.answer}</div>

          {result.evidence_paths.length > 0 && (
            <>
              <h3>引用路徑（{result.evidence_paths.length}）</h3>
              <ul className="result-list">
                {result.evidence_paths.map((p, i) => (
                  <li key={i} className="path-chain">
                    {p.nodes.map((n, j) => (
                      <span key={j}>
                        {j > 0 && ` →(${p.edges[j - 1]?.type}${p.edges[j - 1]?.confidence != null ? ` ${p.edges[j - 1].confidence}` : ""}) `}
                        <Link href={`/node/${encodeURIComponent(n.id)}`}>{n.name}</Link>
                      </span>
                    ))}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
