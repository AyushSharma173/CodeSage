import { useState, useEffect, useRef } from "react";
import ForceGraph2D from 'react-force-graph-2d';

// Recursive node list component
function Node({ node, context, level = 0, seen = new Set() }) {
  const [expanded, setExpanded] = useState(false); // Default collapsed

  if (seen.has(node.node_id)) return null;
  seen.add(node.node_id);

  const indent = level * 20;

  return (
    <div style={{ marginLeft: `${indent}px`, marginBottom: "0.5rem" }}>
      <div
        style={{
          cursor: "pointer",
          fontWeight: "600",
          color: "#111827",
          padding: "0.4rem",
          borderRadius: "6px",
          backgroundColor: "#F3F4F6",
          border: "1px solid #E5E7EB",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        ▶️ {node.node_id} <span style={{ color: "#6B7280" }}>({node.type})</span>
      </div>

      {expanded && node.code && (
        <pre
          style={{
            backgroundColor: "#F9FAFB",
            padding: "0.6rem",
            marginTop: "0.3rem",
            borderRadius: "4px",
            fontSize: "0.9rem",
            whiteSpace: "pre-wrap",
            overflowX: "auto",
            color: "#374151",
            border: "1px solid #E5E7EB",
          }}
        >
          {node.code}
        </pre>
      )}

      {expanded &&
        node.relationships &&
        node.relationships.map((rel) => {
          const child = context.find((n) => n.node_id === rel.target);
          return (
            child && (
              <Node
                key={child.node_id}
                node={child}
                context={context}
                level={level + 1}
                seen={seen}
              />
            )
          );
        })}
    </div>
  );
}

// Viewer component with mode switch
function NodeViewer({ context }) {
    const [viewMode, setViewMode] = useState("list"); // "list" or "graph"
    const graphRef = useRef();
  
    const graphData = {
      nodes: context.map((n) => ({
        id: n.node_id,
        label: `${n.type}: ${n.node_id.split("/").pop()}`,
      })),
      links: context
        .flatMap((n) =>
          (n.relationships || []).map((rel) => ({
            source: n.node_id,
            target: rel.target,
            type: rel.type,
          }))
        )
        .filter((l) => context.some((n) => n.node_id === l.target)),
    };
  
    useEffect(() => {
      if (viewMode === "graph" && graphRef.current) {
        // Zoom-to-fit with padding
        setTimeout(() => {
          graphRef.current.zoomToFit(400, 50); // (ms, padding)
        }, 300); // Delay to ensure layout is ready
      }
    }, [viewMode]);
  
    return (
      <div>
        <div style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <button
            onClick={() => setViewMode("list")}
            style={{
              backgroundColor: viewMode === "list" ? "#2563EB" : "#E5E7EB",
              color: viewMode === "list" ? "white" : "black",
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
            }}
          >
            List
          </button>
          <button
            onClick={() => setViewMode("graph")}
            style={{
              backgroundColor: viewMode === "graph" ? "#2563EB" : "#E5E7EB",
              color: viewMode === "graph" ? "white" : "black",
              padding: "0.5rem 1rem",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
            }}
          >
            Graph
          </button>
          {viewMode === "graph" && (
            <button
              onClick={() => graphRef.current.zoomToFit(400, 50)}
              style={{
                marginLeft: "auto",
                padding: "0.3rem 0.8rem",
                borderRadius: "6px",
                backgroundColor: "#6B7280",
                color: "white",
                border: "none",
                cursor: "pointer",
                fontSize: "0.8rem",
              }}
            >
              🔄 Reset View
            </button>
          )}
        </div>
  
        {viewMode === "list" ? (
          <div style={{ maxHeight: "500px", overflowY: "auto", paddingRight: "0.5rem" }}>
            {context.map((n) => (
              <Node key={n.node_id} node={n} context={context} />
            ))}
          </div>
        ) : (
          <div style={{ height: "500px", border: "1px solid #E5E7EB" }}>
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeLabel="label"
              nodeAutoColorBy="type"
              linkDirectionalArrowLength={4}
              linkDirectionalArrowRelPos={1}
              zoom={2.5}
              minZoom={0.2}
              maxZoom={8}
              cooldownTicks={50}
              onEngineStop={() => graphRef.current.zoomToFit(400, 50)} // Zoom-to-fit once stable
            />
          </div>
        )}
      </div>
    );
  }
  

export default NodeViewer;
