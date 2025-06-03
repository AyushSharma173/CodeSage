# backend/main.py
import traceback
from fastapi import FastAPI, UploadFile, HTTPException, Request
from pydantic import BaseModel
from typing import List
import shutil
import uuid
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from backend.app.repo_handler import clone_repo
from backend.app.graph_builder import build_graph
from backend.app.neo4j_client import Neo4jClient
from backend.app.embedder import embed_graph
from backend.app.vector_store import add_to_vector_store, search_similar_nodes
from backend.app.query_router import answer_query_with_llm

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # <-- frontend origin
    allow_credentials=True,
    allow_methods=["*"],  # <-- allow POST, OPTIONS, etc.
    allow_headers=["*"],
)


ANNOTATED_GRAPH_DIR = "indexed_graphs"
os.makedirs(ANNOTATED_GRAPH_DIR, exist_ok=True)

# ========== Models ==========
class RepoRequest(BaseModel):
    repo_url: str

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    repo_id: str
    strategy: Optional[str] = "invokes_only"  # 👈 add strategy with default

# ========== Endpoints ==========

import pickle
import asyncio
import openai
from backend.app.graph_builder import annotate_graph_async


import re

def sanitize_repo_url(repo_url: str) -> str:
    """
    Turn a GitHub URL into a filesystem‐safe ID.
    E.g. "https://github.com/foo/Bar-Baz.git" -> "Bar-Baz".
    """
    # Remove any trailing “.git”
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[: -len(".git")]
    # Optionally strip out any characters you consider unsafe,
    # e.g. keep only alphanumerics, hyphens and underscores:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", name)

@app.post("/upload-repo")
async def upload_repo(request: RepoRequest):
    openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=600.0)
    repo_url = request.repo_url
    client = Neo4jClient(password="password")  # or from env

    # 1. Compute a safe filename for this repo
    safe_repo_id = sanitize_repo_url(repo_url)
    pickle_path = os.path.join(ANNOTATED_GRAPH_DIR, f"{safe_repo_id}_annotated_graph.pkl")

    try:
        # 2. If we already have that pickle on disk, just load and return
        if os.path.exists(pickle_path):
            with open(pickle_path, "rb") as f:
                G = pickle.load(f)
            if G:
                print(f"Success, repo already indexed and stored")
                return {"status": "success", "message": "Repo already indexed and stored."}

        # 3. Otherwise, clone + build + annotate + save
        repo_path = clone_repo(repo_url)
        G = build_graph(repo_path)

        G = await annotate_graph_async(G, openai_client=openai_client)

        # 4. Save the pickle under our safe path
        with open(pickle_path, "wb") as f:
            pickle.dump(G, f)
            print(f"✅ Annotated graph saved to {pickle_path}")

        # 5. Push the graph to Neo4j (using the safe ID as the repo_id)
        client.push_graph_to_neo4j(G, repo_id=repo_url)
        client.close()

        # 6. Embed and add to vector store
        node_embeddings = await embed_graph(G, openai_client=openai_client)
        add_to_vector_store(node_embeddings, G, repo_url)

        return {"status": "success", "message": "Repo indexed and stored."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/ask")
async def ask_question(req: QueryRequest):
    try:
        client = Neo4jClient(password="password") 

        # 1. Embed query
        results = search_similar_nodes(req.question, top_k=req.top_k, repo_id=req.repo_id)

        # 2. Fetch neighbor nodes from Neo4j
        context_nodes = [r["node_id"] for r in results]
        print("[!] Context nodes:", context_nodes)
        graph_context = client.query_neo4j_neighbors(context_nodes, repo_id=req.repo_id, depth=2, strategy=req.strategy or "invokes_only")

        # 3. Call LLM to answer using graph context
        answer = answer_query_with_llm(req.question, graph_context)

        return {"answer": answer, "context": graph_context}
        # return {"context": graph_context}
    except Exception as e:
        print("[!] Exception in /ask:", e)
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/stats")
async def get_graph_stats():
    try:
        from app.neo4j_client import get_graph_statistics
        return get_graph_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))