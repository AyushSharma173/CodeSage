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
    # ─── User‐adjustable query parameters ─────────────────────────────────────────
    question = "count nodes function?"
    top_k = 5
    repo_id = "https://github.com/AyushSharma173/CodeSage.git"


    # strategy = "invokes_only"
    # depth = 2
    # # New hyperparameters for graph traversal:
    # edge_types = ["invokes", "contains"]            # which edge 'type' values to follow
    # include_node_types = ["file", "function"]       # restrict to these node types
    # directed = True                                 # treat edges as directed (True) or undirected (False)
    # include_incoming = True                         # include edges pointing INTO the seed
    # include_outgoing = True                         # include edges pointing OUT FROM the seed


    strategy = "default_bfs_all"        # (this is just a label; effectively we override everything below)
    depth = 3                           # or any number of hops you care about
    edge_types = None                   # means “no filter on edge.type; follow _all_ edge types”
    include_node_types = None           # means “no filter on node.type; include _all_ nodes”
    directed = False                    # treat edges as undirected
    include_outgoing = True             # include edges in both directions
    include_incoming = True


    try:
        client = Neo4jClient(password="password")

        # 1) Print counts in the database for sanity check
        print("Total nodes for this repo:   ", client.count_nodes())
        print("Total relationships for this repo:", client.count_rels())

        # 2) Embed the question and retrieve top‐k nearest nodes from Qdrant
        results = search_similar_nodes(question, top_k=top_k, repo_id=repo_id)

        # 2a) Neatly print all retrieved points
        print("\n=== Retrieved nodes (top_k results) ===")
        for idx, r in enumerate(results, start=1):
            print(f"Node {idx}:")
            print(f"  node_id   : {r['node_id']}")
            print(f"  summary   : {r['summary']!r}")
            print(f"  repo_id   : {r['repo_id']}")
            print(f"  type      : {r['type']}")
            print(f"  file_path : {r['file_path']}")
            print(f"  start_line: {r['start_line']}")
            print(f"  end_line  : {r['end_line']}")
            print(f"  score     : {r['score']:.4f}")
            print("-" * 40)

        # 3) Gather just the node_ids as seeds for Neo4j traversal
        context_nodes = [r["node_id"] for r in results]
        print("\n=== Context nodes passed to Neo4j ===")
        for n in context_nodes:
            print(f"  • {n}")
        print()

        # 4) Fetch neighbor nodes according to all hyperparameters
        graph_context = client.query_neo4j_neighbors(
            node_ids=context_nodes,
            repo_id=repo_id,
            depth=depth,
            strategy=strategy,
            edge_types=edge_types,
            include_node_types=include_node_types,
            directed=directed,
            include_incoming=include_incoming,
            include_outgoing=include_outgoing,
        )

        # 5) Neatly print the final graph_context returned
        print("\n=== Final graph_context nodes ===")
        for idx, node in enumerate(graph_context, start=1):
            print(f"Context Node {idx}:")
            print(f"  node_id   : {node.get('node_id')}")
            print(f"  type      : {node.get('type')}")
            print(f"  file_path : {node.get('file_path')}")
            sl = node.get("start_line")
            el = node.get("end_line")
            if sl is not None and el is not None:
                print(f"  lines     : {sl}–{el}")
            else:
                print(f"  lines     : <n/a>")

            # Code snippet preview (up to 3 lines or ~100 chars)
            code_snippet = node.get("code", "").strip()
            if code_snippet:
                snippet_lines = code_snippet.splitlines()[:3]
                preview = "\n".join(snippet_lines)
                if len(preview) > 100:
                    preview = preview[:100] + "…"
                print("  code (snippet):")
                for line in preview.splitlines():
                    print(f"    {line}")
            else:
                print("  code (snippet): <none>")

            # Print relationships (if any)
            rels = node.get("relationships", [])
            if rels:
                print("  relationships:")
                for rel in rels:
                    print(f"    └─ ({rel['type']}) → {rel['target']}")
            else:
                print("  relationships: []")
            print("-" * 60)

        # 6) Call LLM to answer using the assembled graph_context
        answer = answer_query_with_llm(question, graph_context)
        print(f"\nAnswer: {answer}")

    except Exception as e:
        print("[!] Exception in test script:", e)
        traceback.print_exc()
    finally:
        client.close()
    