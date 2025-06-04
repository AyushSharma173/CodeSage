// src/NodeViewer.jsx
import React from "react";
import ReactMarkdown from "react-markdown";
import "./NodeViewer.css"; // if you have any custom CSS

export default function NodeViewer({ context = [] }) {
  if (!Array.isArray(context) || context.length === 0) {
    return (
      <div style={{ color: "#6B7280", fontStyle: "italic" }}>
        No context to display.
      </div>
    );
  }

  return (
    <div style={{ padding: "0.5rem", overflowY: "auto" }}>
      {context.map((node, idx) => (
        <div
          key={idx}
          style={{
            marginBottom: "1rem",
            padding: "0.75rem",
            backgroundColor: "#FFFFFF",
            border: "1px solid #E5E7EB",
            borderRadius: "6px",
            textAlign: "left",
          }}
        >
          <div
            style={{
              fontWeight: 600,
              color: "#1F2937",
              marginBottom: "0.25rem",
            }}
          >
            {node.node_id} <span style={{ color: "#6B7280" }}>({node.type})</span>
          </div>
          <div style={{ fontSize: "0.9rem", color: "#374151", marginBottom: "0.5rem" }}>
            {node.file_path}{" "}
            {node.start_line != null && node.end_line != null
              ? ` lines ${node.start_line}–${node.end_line}`
              : ""}
          </div>
          {node.code ? (
            <pre
              style={{
                fontSize: "0.85rem",
                backgroundColor: "#F3F4F6",
                padding: "0.5rem",
                borderRadius: "4px",
                overflowX: "auto",
              }}
            >
              {node.code.split("\n").slice(0, 3).join("\n")}
              {node.code.split("\n").length > 3 ? "…" : ""}
            </pre>
          ) : null}

          {node.relationships?.length > 0 && (
            <div style={{ marginTop: "0.5rem" }}>
              <strong style={{ fontSize: "0.9rem", color: "#1F2937" }}>
                Relationships:
              </strong>
              <ul style={{ paddingLeft: "1.25rem", marginTop: "0.25rem" }}>
                {node.relationships.map((r, i) => (
                  <li key={i} style={{ fontSize: "0.85rem", color: "#4B5563" }}>
                    <code>{r.type}</code> → <code>{r.target}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
