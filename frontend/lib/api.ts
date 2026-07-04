export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

export interface SearchResult {
  id: string;
  type: string;
  name: string;
  english_name: string | null;
  ticker: string | null;
  exchange: string | null;
  is_listed_in_tw: boolean | null;
  description: string | null;
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
  ticker?: string | null;
  is_listed_in_tw?: boolean | null;
  category?: string | null;
}

export interface GraphEdge {
  id: string;
  type: string;
  from: string;
  to: string;
  description?: string | null;
  confidence?: number | null;
  status?: string | null;
  period?: string | null;
  product_id?: string | null;
}

export interface NeighborhoodResponse {
  center: string;
  depth: number;
  direction: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface NodeDetail {
  id: string;
  type: string;
  properties: Record<string, unknown>;
  out_degree: number;
  in_degree: number;
  relationship_summary: { rel_type: string; direction: string; count: number }[];
}

export interface EdgeDetail {
  id: string;
  type: string;
  from: { id: string; name: string; type: string };
  to: { id: string; name: string; type: string };
  properties: Record<string, unknown>;
  sources: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
}

export interface DemandShockCompany {
  company_id: string;
  name: string;
  ticker: string | null;
  exchange: string | null;
  is_listed_in_tw: boolean | null;
  score: number;
  factors: {
    path_confidence: number;
    path_decay: number;
    hops: number;
    exposure_score: string;
    demand_relevance: string;
  };
  path: {
    nodes: { id: string; name: string; type: string }[];
    edges: { id: string; type: string; from: string; to: string; confidence: number | null }[];
  };
}

export interface DemandShockResponse {
  target: { id: string; name: string; type: string };
  depth: number;
  shock_direction?: "increase" | "decrease";
  impact?: string;
  affected_companies: DemandShockCompany[];
}

export interface SupplyDisruptionCompany extends DemandShockCompany {
  has_alternative: boolean;
}

export interface SupplyDisruptionResponse {
  target: { id: string; name: string; type: string };
  depth: number;
  impact: string;
  affected_companies: SupplyDisruptionCompany[];
}

export interface KeyNode {
  id: string;
  name: string;
  type: string;
  ticker: string | null;
  total_degree: number;
  in_degree: number;
  out_degree: number;
}

export interface Bottleneck {
  product_id: string;
  name: string;
  producers: { id: string; name: string; ticker: string | null; is_listed_in_tw: boolean | null }[];
  producer_count: number;
  downstream_usage: number;
}

export interface ConcentrationEntry {
  company_id: string;
  name: string;
  ticker: string | null;
  edge_count: number;
  weight: number;
  share: number;
  edges: { id: string; type: string; confidence: number | null; product_id: string | null }[];
}

export interface ConcentrationResponse {
  company: { id: string; name: string };
  basis: string;
  revenue_share: string;
  suppliers: ConcentrationEntry[];
  customers: ConcentrationEntry[];
}

export interface ReviewCandidate {
  id: string;
  type: string;
  from: { id: string; name: string; type: string };
  to: { id: string; name: string; type: string };
  properties: Record<string, unknown>;
  sources: Record<string, unknown>[];
}
