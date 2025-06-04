// src/RetrievalSettings.jsx
import React from "react";
import "./RetrievalSettings.css";

export default function RetrievalSettings({
  strategy,
  setStrategy,
  depth,
  setDepth,
  edgeTypes,
  setEdgeTypes,
  includeNodeTypes,
  setIncludeNodeTypes,
  directed,
  setDirected,
  includeIncoming,
  setIncludeIncoming,
  includeOutgoing,
  setIncludeOutgoing,
  strategyOptions,
  allEdgeTypes,
  allNodeTypes,
  toggleSelection,
}) {
  return (
    <aside className="rs-aside">
      <h4 className="rs-sidebar-title">Retrieval Settings</h4>

      {/* ── Strategy Dropdown ── */}
      <div className="rs-card">
        <h5 className="rs-card-title">General</h5>
        <div className="rs-field">
          <label htmlFor="strategy" className="rs-label">
            Strategy
          </label>
          <select
            id="strategy"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            className="rs-select"
          >
            {strategyOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* ── Depth Input ── */}
        <div className="rs-field">
          <label htmlFor="depth" className="rs-label">
            Depth (hops)
          </label>
          <input
            id="depth"
            type="number"
            min={1}
            max={5}
            value={depth}
            onChange={(e) => setDepth(parseInt(e.target.value) || 1)}
            className="rs-input"
          />
        </div>
      </div>

      {/* ── Filters: Edge Types & Node Types ── */}
      <div className="rs-card">
        <h5 className="rs-card-title">Filters</h5>

        {/* Edge Types */}
        <div className="rs-field">
          <label className="rs-label">Edge Types</label>
          <div className="rs-checkbox-list">
            {allEdgeTypes.map((opt) => (
              <label key={opt.value} className="rs-checkbox-item">
                <input
                  type="checkbox"
                  checked={edgeTypes.includes(opt.value)}
                  onChange={() => toggleSelection(opt.value, edgeTypes, setEdgeTypes)}
                />
                <span className="rs-checkbox-label">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Include Node Types */}
        <div className="rs-field">
          <label className="rs-label">Include Node Types</label>
          <div className="rs-checkbox-list">
            {allNodeTypes.map((opt) => (
              <label key={opt.value} className="rs-checkbox-item">
                <input
                  type="checkbox"
                  checked={includeNodeTypes.includes(opt.value)}
                  onChange={() =>
                    toggleSelection(opt.value, includeNodeTypes, setIncludeNodeTypes)
                  }
                />
                <span className="rs-checkbox-label">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* ── Directionality ── */}
      <div className="rs-card">
        <h5 className="rs-card-title">Directionality</h5>
        <div className="rs-checkbox-item-full">
          <input
            type="checkbox"
            checked={directed}
            onChange={() => setDirected((prev) => !prev)}
          />
          <span className="rs-checkbox-label">Directed</span>
        </div>
        <div className="rs-checkbox-item-full">
          <input
            type="checkbox"
            checked={includeIncoming}
            onChange={() => setIncludeIncoming((prev) => !prev)}
          />
          <span className="rs-checkbox-label">Include Incoming</span>
        </div>
        <div className="rs-checkbox-item-full">
          <input
            type="checkbox"
            checked={includeOutgoing}
            onChange={() => setIncludeOutgoing((prev) => !prev)}
          />
          <span className="rs-checkbox-label">Include Outgoing</span>
        </div>
      </div>
    </aside>
  );
}
