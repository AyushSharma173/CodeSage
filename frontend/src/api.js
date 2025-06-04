// src/api.js
const BASE_URL = "http://localhost:8000";

export async function uploadRepo(repoUrl) {
  const res = await fetch(`${BASE_URL}/upload-repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to upload repo");
  }
  return res.json();
}

export async function askQuestion(payload) {
  // payload should look like:
  // {
  //   question: "...",
  //   top_k: 5,
  //   repo_id: "...",
  //   strategy: "...",
  //   depth: 2,
  //   edge_types: [...],
  //   include_node_types: [...],
  //   directed: true,
  //   include_incoming: true,
  //   include_outgoing: true
  // }
  const res = await fetch(`${BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to get answer");
  }
  return res.json();
}

/**
 * Fetch the entire graph (all nodes + edges) for a given repo_id.
 * Returns { nodes: [...], edges: [...] } exactly as the backend emits.
 */
export async function getFullGraph(repoId) {
  const res = await fetch(`${BASE_URL}/graph/${encodeURIComponent(repoId)}`, {
    method: "GET",
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to load full graph");
  }
  return res.json();
}
