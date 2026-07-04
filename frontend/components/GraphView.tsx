"use client";

import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";
import { GraphEdge, GraphNode } from "@/lib/api";

const NODE_COLORS: Record<string, string> = {
  Company: "#1d4ed8",
  Product: "#059669",
  Industry: "#d97706",
  Application: "#dc2626",
};

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerId: string;
  onSelectNode: (id: string) => void;
  onSelectEdge: (id: string) => void;
}

export default function GraphView({ nodes, edges, centerId, onSelectNode, onSelectEdge }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...nodes.map((n) => ({
          data: { id: n.id, label: n.name ?? n.id, type: n.type, isCenter: n.id === centerId, status: n.status ?? "" },
        })),
        ...edges.map((e) => ({
          data: { id: e.id, source: e.from, target: e.to, label: e.type, status: e.status ?? "" },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 11,
            color: "#1e293b",
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: 28,
            height: 28,
            "background-color": (el: cytoscape.NodeSingular) =>
              NODE_COLORS[el.data("type") as string] ?? "#64748b",
            "border-width": (el: cytoscape.NodeSingular) =>
              el.data("isCenter") ? 4 : el.data("status") === "candidate" ? 2 : 0,
            "border-color": (el: cytoscape.NodeSingular) =>
              el.data("isCenter") ? "#facc15" : "#94a3b8",
            "border-style": (el: cytoscape.NodeSingular) =>
              !el.data("isCenter") && el.data("status") === "candidate" ? "dashed" : "solid",
            opacity: (el: cytoscape.NodeSingular) => (el.data("status") === "candidate" ? 0.75 : 1),
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            "font-size": 8,
            color: "#94a3b8",
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.9,
            width: 1.5,
            "line-color": "#cbd5e1",
            "target-arrow-color": "#cbd5e1",
            "line-style": (el: cytoscape.EdgeSingular) =>
              el.data("status") === "candidate" ? "dashed" : "solid",
          },
        },
        { selector: ":selected", style: { "overlay-color": "#facc15", "overlay-opacity": 0.25 } },
      ],
      layout: { name: "cose", animate: false, padding: 30 },
    });

    cy.on("tap", "node", (evt) => onSelectNode(evt.target.id()));
    cy.on("tap", "edge", (evt) => onSelectEdge(evt.target.id()));

    return () => cy.destroy();
  }, [nodes, edges, centerId, onSelectNode, onSelectEdge]);

  return <div ref={containerRef} className="graph-canvas" />;
}
