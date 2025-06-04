// src/GraphView.jsx
import React, { useEffect, useState, useRef } from "react";
import { getFullGraph } from "./api";
import ForceGraph2D from "react-force-graph-2d";

export default function GraphView({ repoId, onClose }) {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const fgRef = useRef();

  useEffect(() => {
    // As soon as this component mounts, fetch the full graph from the backend.
    getFullGraph(repoId)
      .then((data) => {
        // data looks like: { nodes: [...], edges: [...] }
        // react-force-graph expects { nodes: [...], links: [...] }
        setGraphData({
          nodes: data.nodes,
          links: data.edges.map((e) => ({
            source: e.source,
            target: e.target,
            type: e.type,
          })),
        });
      })
      .catch((err) => {
        console.error("Error loading full graph:", err);
      });
  }, [repoId]);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.5)",
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Close button */}
      <div style={{ padding: "8px", textAlign: "right", background: "#FFFFFF" }}>
        <button
          onClick={onClose}
          style={{
            padding: "6px 12px",
            backgroundColor: "#EF4444",
            color: "#FFFFFF",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Close
        </button>
      </div>

      {/* Force-graph area */}
      <div style={{ flex: 1, background: "#FFFFFF" }}>
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeAutoColorBy="type"
          linkDirectionalParticles={2}
          linkDirectionalParticleSpeed={0.005}
          linkWidth={(link) => (link.type === "contains" ? 1 : 1.5)}
          nodeLabel={(node) =>
            `${node.id}\nType: ${node.type}\nFile: ${node.file_path}`
          }
          linkLabel={(link) => link.type}
          nodeCanvasObject={(node, ctx, globalScale) => {
            // Draw a small circle plus a short label (last path segment)
            const label = node.id.split("/").pop().split(":").pop();
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "#000000";
            ctx.fillText(label, node.x, node.y + 6 / globalScale);

            ctx.beginPath();
            ctx.arc(node.x, node.y, 4 / globalScale, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.color;
            ctx.fill();
          }}
        />
      </div>
    </div>
  );
}
