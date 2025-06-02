import requests


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

from backend.app.neo4j_client import Neo4jClient
from backend.app.vector_store import search_similar_nodes
from backend.app.query_router import answer_query_with_llm







if __name__ == "__main__":
    question = "count nodes function?"
    top_k = 5
    repo_id = "https://github.com/AyushSharma173/CodeSage.git"
    strategy = "invokes_only"

    client = Neo4jClient(password="password") 

    print("Total nodes for this repo:", client.count_nodes())
    print("Total relationships for this repo:", client.count_rels())

    # 1. Embed query
    results = search_similar_nodes(question, top_k=top_k, repo_id=repo_id)

    # # 1a. Neatly print all retrieved points (for debugging)
    # print("=== Retrieved nodes (top_k results) ===")
    # for idx, r in enumerate(results, start=1):
    #     print(f"Node {idx}:")
    #     print(f"  node_id   : {r['node_id']}")
    #     print(f"  summary   : {r['summary']}")
    #     print(f"  repo_id   : {r['repo_id']}")
    #     print(f"  type      : {r['type']}")
    #     print(f"  file_path : {r['file_path']}")
    #     print(f"  start_line: {r['start_line']}")
    #     print(f"  end_line  : {r['end_line']}")
    #     print(f"  score     : {r['score']:.4f}")
    #     print("-" * 40)

    # 2. Fetch neighbor nodes from Neo4j
    context_nodes = [r["node_id"] for r in results]
    print("\n=== Context nodes passed to Neo4j ===")
    for n in context_nodes:
        print(f"  • {n}")
    print()


    graph_context = client.query_neo4j_neighbors(context_nodes, repo_id=repo_id, depth=2, strategy=strategy)

    # ============================
    # Neatly print the final graph_context
    # ============================
    # print("\n=== Final graph_context nodes ===")
    # for idx, node in enumerate(graph_context, start=1):
    #     print(f"Context Node {idx}:")
    #     print(f"  node_id   : {node.get('node_id')}")
    #     print(f"  type      : {node.get('type')}")
    #     print(f"  file_path : {node.get('file_path')}")
    #     print(f"  start_line: {node.get('start_line')}")
    #     print(f"  end_line  : {node.get('end_line')}")
    #     # If you want to see a snippet of the code, you can print the first ~100 characters:
    #     code_snippet = node.get('code', "")
    #     if code_snippet:
    #         snippet = code_snippet.strip().splitlines()
    #         # show up to first 3 lines or 100 chars total
    #         preview = "\n".join(snippet[:3])
    #         if len(preview) > 100:
    #             preview = preview[:100] + "…"
    #         print(f"  code (snippet):\n    {preview.replace(chr(10), chr(10)+'    ')}")
    #     else:
    #         print(f"  code (snippet): <no code>")

    #     rels = node.get("relationships", [])
    #     if rels:
    #         print(f"  relationships:")
    #         for r in rels:
    #             # r["type"] is the relationship type (e.g. "invokes", "inherits")
    #             # r["target"] is the node_id of the neighbor
    #             print(f"    └─ ({r['type']}) → {r['target']}")
    #     else:
    #         print(f"  relationships: []")

    #     print("-" * 50)


    # 3. Call LLM to answer using graph context
    answer = answer_query_with_llm(question, graph_context)

    # print(f"Answer: {answer}")
    