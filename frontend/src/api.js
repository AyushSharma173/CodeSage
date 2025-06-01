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

export async function askQuestion(question, repoId, topK = 5, strategy = "invokes_only") {
  const res = await fetch(`${BASE_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: topK, repo_id: repoId, strategy }),
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to get answer");
  }

  return res.json();
}

