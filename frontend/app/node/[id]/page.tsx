"use client";

import { useCallback, useEffect, useState } from "react";
import GraphView from "@/components/GraphView";
import {
  api,
  EdgeDetail,
  NeighborhoodResponse,
  NodeDetail,
} from "@/lib/api";

const REL_TYPE_GROUPS: Record<string, string[]> = {
  "供應/代工": ["SUPPLIES_TO", "MANUFACTURES_FOR", "ASSEMBLES_FOR"],
  "生產/銷售": ["PRODUCES", "SELLS", "USES", "DISTRIBUTES", "ASSEMBLES"],
  "產品鏈": ["COMPONENT_OF", "INPUT_OF", "SUBSTITUTE_FOR", "USED_WITH"],
  "應用/需求": ["USED_IN", "ENABLES", "DRIVES_DEMAND_FOR", "INCREASES_DEMAND_FOR", "DECREASES_DEMAND_FOR"],
  "產業/其他": ["BELONGS_TO", "COMPETES_WITH", "OWNS", "INVESTS_IN"],
};

function PropList({ props }: { props: Record<string, unknown> }) {
  const hidden = new Set(["id"]);
  return (
    <dl>
      {Object.entries(props)
        .filter(([k, v]) => !hidden.has(k) && v !== null && v !== undefined && v !== "")
        .map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{Array.isArray(v) ? v.join("; ") : String(v)}</dd>
          </div>
        ))}
    </dl>
  );
}

export default function NodePage({ params }: { params: { id: string } }) {
  const nodeId = decodeURIComponent(params.id);
  const [depth, setDepth] = useState(1);
  const [direction, setDirection] = useState("both");
  const [minConfidence, setMinConfidence] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [activeGroups, setActiveGroups] = useState<string[]>(Object.keys(REL_TYPE_GROUPS));

  const [graph, setGraph] = useState<NeighborhoodResponse | null>(null);
  const [nodeDetail, setNodeDetail] = useState<NodeDetail | null>(null);
  const [edgeDetail, setEdgeDetail] = useState<EdgeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const types = activeGroups.flatMap((g) => REL_TYPE_GROUPS[g]);
    const qs = new URLSearchParams({
      node_id: nodeId,
      depth: String(depth),
      direction,
      relationship_types: types.join(","),
    });
    if (minConfidence > 0) qs.set("min_confidence", String(minConfidence));
    if (statusFilter) qs.set("status", statusFilter);
    api<NeighborhoodResponse>(`/api/graph/neighborhood?${qs}`)
      .then((data) => { setGraph(data); setError(null); })
      .catch((err) => setError(String(err)));
  }, [nodeId, depth, direction, minConfidence, statusFilter, activeGroups]);

  useEffect(() => {
    api<NodeDetail>(`/api/nodes/${encodeURIComponent(nodeId)}`)
      .then(setNodeDetail)
      .catch(() => setNodeDetail(null));
  }, [nodeId]);

  const onSelectNode = useCallback((id: string) => {
    setEdgeDetail(null);
    api<NodeDetail>(`/api/nodes/${encodeURIComponent(id)}`).then(setNodeDetail).catch(() => null);
  }, []);

  const onSelectEdge = useCallback((id: string) => {
    api<EdgeDetail>(`/api/edges/${encodeURIComponent(id)}`).then(setEdgeDetail).catch(() => null);
  }, []);

  function toggleGroup(g: string) {
    setActiveGroups((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]));
  }

  return (
    <div>
      <h1>
        Focus Graph：{nodeDetail?.properties?.name ? String(nodeDetail.properties.name) : nodeId}
        {nodeDetail && <span className={`badge ${nodeDetail.type}`} style={{ marginLeft: 8 }}>{nodeDetail.type}</span>}
      </h1>

      <div className="controls">
        <label>
          深度
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            <option value={1}>1-hop</option>
            <option value={2}>2-hop</option>
            <option value={3}>3-hop</option>
          </select>
        </label>
        <label>
          方向
          <select value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="both">全部</option>
            <option value="upstream">上游</option>
            <option value="downstream">下游</option>
          </select>
        </label>
        <label>
          最低可信度
          <input
            type="number" min={0} max={1} step={0.1} value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            style={{ width: 64 }}
          />
        </label>
        <label>
          狀態
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">全部</option>
            <option value="verified">verified</option>
            <option value="candidate">candidate</option>
          </select>
        </label>
        {Object.keys(REL_TYPE_GROUPS).map((g) => (
          <label key={g}>
            <input type="checkbox" checked={activeGroups.includes(g)} onChange={() => toggleGroup(g)} />
            {g}
          </label>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      <div className="graph-layout">
        {graph && (
          <GraphView
            nodes={graph.nodes}
            edges={graph.edges}
            centerId={nodeId}
            onSelectNode={onSelectNode}
            onSelectEdge={onSelectEdge}
          />
        )}
        <aside className="side-panel">
          {edgeDetail ? (
            <>
              <h2>關係詳情</h2>
              <p>
                <strong>{edgeDetail.from.name}</strong>
                {" —[" + edgeDetail.type + "]→ "}
                <strong>{edgeDetail.to.name}</strong>
              </p>
              <PropList props={edgeDetail.properties} />
              {edgeDetail.sources.length > 0 && (
                <>
                  <h2>來源</h2>
                  {edgeDetail.sources.map((s, i) => (
                    <p key={i} className="muted">{String(s.title ?? s.id)}（{String(s.type ?? "")}）</p>
                  ))}
                </>
              )}
              <p><button onClick={() => setEdgeDetail(null)}>← 回節點資訊</button></p>
            </>
          ) : nodeDetail ? (
            <>
              <h2>節點詳情</h2>
              <PropList props={nodeDetail.properties} />
              <dl>
                <dt>連出 / 連入</dt>
                <dd>{nodeDetail.out_degree} / {nodeDetail.in_degree}</dd>
                <dt>關係摘要</dt>
                <dd>
                  {nodeDetail.relationship_summary.map((r) => (
                    <div key={`${r.rel_type}-${r.direction}`}>
                      {r.direction === "out" ? "→" : "←"} {r.rel_type} × {r.count}
                    </div>
                  ))}
                </dd>
              </dl>
            </>
          ) : (
            <p className="muted">點選節點或邊查看詳情。</p>
          )}
        </aside>
      </div>
      <p className="muted">
        實線 = verified，虛線 = candidate。節點顏色：藍 = 公司、綠 = 產品、橘 = 產業、紅 = 應用。
      </p>
    </div>
  );
}
