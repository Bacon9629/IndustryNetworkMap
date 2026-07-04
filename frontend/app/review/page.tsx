"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ReviewCandidate } from "@/lib/api";

const REL_TYPES = [
  "SUPPLIES_TO", "MANUFACTURES_FOR", "ASSEMBLES_FOR", "COMPETES_WITH", "OWNS", "INVESTS_IN",
  "PRODUCES", "SELLS", "USES", "DISTRIBUTES", "ASSEMBLES", "BELONGS_TO",
  "COMPONENT_OF", "INPUT_OF", "SUBSTITUTE_FOR", "USED_WITH",
  "USED_IN", "ENABLES", "DRIVES_DEMAND_FOR", "INCREASES_DEMAND_FOR", "DECREASES_DEMAND_FOR",
];

export default function ReviewPage() {
  const [relType, setRelType] = useState("");
  const [createdBy, setCreatedBy] = useState("");
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<ReviewCandidate[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  const [editConfidence, setEditConfidence] = useState("");
  const [editNote, setEditNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const qs = new URLSearchParams({ limit: "100" });
    if (relType) qs.set("rel_type", relType);
    if (createdBy) qs.set("created_by", createdBy);
    try {
      const data = await api<{ total: number; candidates: ReviewCandidate[] }>(`/api/review/candidates?${qs}`);
      setTotal(data.total);
      setItems(data.candidates);
      setError(null);
    } catch (err) {
      setError(String(err));
    }
  }, [relType, createdBy]);

  useEffect(() => { load(); }, [load]);

  async function act(id: string, action: "accept" | "reject") {
    try {
      await api(`/api/review/candidates/${encodeURIComponent(id)}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      setMessage(`${id} 已${action === "accept" ? "接受（verified）" : "拒絕（rejected）"}`);
      load();
    } catch (err) {
      setError(String(err));
    }
  }

  function startEdit(c: ReviewCandidate) {
    setEditing(c.id);
    setEditConfidence(String(c.properties.confidence ?? ""));
    setEditNote(String(c.properties.note ?? ""));
  }

  async function saveEdit(id: string) {
    const body: Record<string, unknown> = {};
    if (editConfidence !== "") body.confidence = Number(editConfidence);
    if (editNote !== "") body.note = editNote;
    try {
      await api(`/api/review/candidates/${encodeURIComponent(id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setEditing(null);
      setMessage(`${id} 已更新`);
      load();
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div>
      <h1>候選關係審核（{total}）</h1>

      <div className="controls">
        <label>
          關係類型
          <select value={relType} onChange={(e) => setRelType(e.target.value)}>
            <option value="">全部</option>
            {REL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label>
          建立者
          <select value={createdBy} onChange={(e) => setCreatedBy(e.target.value)}>
            <option value="">全部</option>
            <option value="manual_seed">manual_seed</option>
            <option value="llm_extraction">llm_extraction</option>
          </select>
        </label>
        <button onClick={load}>重新整理</button>
      </div>

      {error && <p className="error">{error}</p>}
      {message && <p className="muted">{message}</p>}

      <table className="shock-table">
        <thead>
          <tr>
            <th>關係</th>
            <th>confidence</th>
            <th>來源 / evidence</th>
            <th>備註</th>
            <th style={{ width: 220 }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td>
                <Link href={`/node/${encodeURIComponent(c.from.id)}`}>{c.from.name}</Link>
                <span className="muted"> —[{c.type}]→ </span>
                <Link href={`/node/${encodeURIComponent(c.to.id)}`}>{c.to.name}</Link>
                <div className="muted">{c.id}・{String(c.properties.created_by ?? "")}</div>
              </td>
              <td>
                {editing === c.id ? (
                  <input
                    type="number" min={0} max={1} step={0.05} value={editConfidence}
                    onChange={(e) => setEditConfidence(e.target.value)} style={{ width: 70 }}
                  />
                ) : (
                  String(c.properties.confidence ?? "—")
                )}
              </td>
              <td className="muted">
                {c.sources.map((s, i) => <div key={i}>{String(s.title ?? s.id)}</div>)}
                {c.properties.evidence ? <div>「{String(c.properties.evidence)}」</div> : null}
              </td>
              <td className="muted">
                {editing === c.id ? (
                  <input value={editNote} onChange={(e) => setEditNote(e.target.value)} style={{ width: 160 }} />
                ) : (
                  String(c.properties.note ?? "")
                )}
              </td>
              <td>
                {editing === c.id ? (
                  <>
                    <button onClick={() => saveEdit(c.id)}>儲存</button>{" "}
                    <button onClick={() => setEditing(null)}>取消</button>
                  </>
                ) : (
                  <>
                    <button className="primary" onClick={() => act(c.id, "accept")}>接受</button>{" "}
                    <button onClick={() => startEdit(c)}>修改</button>{" "}
                    <button onClick={() => act(c.id, "reject")}>拒絕</button>
                  </>
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={5} className="muted">目前沒有待審核的 candidate 關係。</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
