from openai import OpenAI
import networkx as nx
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create a single OpenAI client instance
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # Set your key in env vars or explicitly


# def embed_graph(G: nx.MultiDiGraph, model: str = "text-embedding-3-small") -> dict:
#     """
#     Given a graph `G`, compute OpenAI embeddings for each node.
#     Returns a dictionary mapping node ID -> embedding vector (list of floats).
#     """
#     embeddings = {}

#     for node_id, data in G.nodes(data=True):
#         node_type = data.get("type", "unknown")
#         summary = data.get("summary", "").strip()
#         code = data.get("code", "").strip()
#         file_path = data.get("file_path", "")
#         start_line = data.get("start_line", "")
#         end_line = data.get("end_line", "")

#         # Prefer concise summary if available, fallback to code and metadata
#         if summary:
#             input_text = f"Node ID: {node_id}\nType: {node_type}\nFile: {file_path}\nSummary:\n{summary}"
#         else:
#             input_text = (
#                 f"Node ID: {node_id}\nType: {node_type}\nFile: {file_path}\n"
#                 f"Code:\n{code}\nLines: {start_line}-{end_line}"
#             )


#         try:
#             response = client.embeddings.create(
#                 input=input_text,
#                 model=model
#             )
#             embeddings[node_id] = response.data[0].embedding
#         except Exception as e:
#             print(f"[!] Embedding failed for node {node_id}: {e}")

#     return embeddings


import tiktoken
import asyncio

sem = asyncio.Semaphore(8)
MAX_TOKENS = 8191  # adjust based on model

async def embed_graph(G: nx.MultiDiGraph, openai_client: OpenAI, model: str = "text-embedding-3-small") -> dict:
    tokenizer = tiktoken.encoding_for_model(model)
    embeddings: dict[str, list[float]] = {}
    lock = asyncio.Lock()
    completed = 0

    # Pre-filter nodes if you want (only those with type/summary/etc)
    valid_nodes = [
        (node_id, data)
        for node_id, data in G.nodes(data=True)
        if isinstance(data, dict)
    ]
    total = len(valid_nodes)

    async def embed_node(node_id: str, data: dict):
        nonlocal completed

        # build your input
        node_type = data.get("type", "unknown")
        summary   = data.get("summary", "").strip()
        code      = data.get("code", "").strip()
        fp        = data.get("file_path", "")
        sl        = data.get("start_line", "")
        el        = data.get("end_line", "")

        if summary:
            input_text = f"Node ID: {node_id}\nType: {node_type}\nFile: {fp}\nSummary:\n{summary}"
        else:
            input_text = (
                f"Node ID: {node_id}\nType: {node_type}\nFile: {fp}\n"
                f"Code:\n{code}\nLines: {sl}-{el}"
            )

        # truncate
        tokens = tokenizer.encode(input_text)
        if len(tokens) > MAX_TOKENS:
            input_text = tokenizer.decode(tokens[:MAX_TOKENS])

        try:
            async with sem:
                resp = await openai_client.embeddings.create(input=input_text, model=model)
            async with lock:
                embeddings[node_id] = resp.data[0].embedding
        except Exception as e:
            print(f"[❌] Failed to embed {node_id}: {e}")

        # progress update
        async with lock:
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(f"[{completed}/{total}] embeddings done")

    # launch all tasks
    print(f"🚀 Launching embedding tasks for {total} nodes…")
    tasks = [embed_node(nid, data) for nid, data in valid_nodes]
    await asyncio.gather(*tasks)
    print("✅ All embeddings complete.")

    return embeddings



if __name__ == "__main__":
    # I want to test the embedder with a simple graph
    G = nx.MultiDiGraph()
    G.add_node("1", type="function", code="def hello_world(): print('Hello, World!')", start_line="1", end_line="2")
    G.add_node("2", type="function", code="def goodbye_world(): print('Goodbye, World!')", start_line="1", end_line="2")
    G.add_edge("1", "2", type="calls")
    embeddings = embed_graph(G)
    print(embeddings)
    