import requests
import os

def call_ask_endpoint(question: str, repo_id: str):
    url = "http://localhost:8000/ask"
    payload = {
        "question": question,
        "top_k": 2,
        "repo_id": repo_id
    }

    try:
        response = requests.post(url, json=payload)
        print("Status code:", response.status_code)
        print("Response JSON:", response.json())
        return response.json()
    except Exception as e:
        print("[!] Failed to call /ask:", e)



def call_upload_repo_endpoint(repo_url: str):
    url = "http://localhost:8000/upload-repo"
    payload = {
        "repo_url": repo_url
    }

    try:
        response = requests.post(url, json=payload)
        print("Status code:", response.status_code)
        print("Response JSON:", response.json())
    except Exception as e:
        print("[!] Failed to call /upload-repo:", e)

from collections import defaultdict



if __name__ == "__main__2":
    from backend.app.repo_handler import clone_repo
    from backend.app.graph_builder import build_graph, annotate_graph_async
    from backend.app.embedder import embed_graph
    from backend.app.vector_store import add_to_vector_store
    import asyncio
    import openai
    import pickle


    import pickle

    # with open("annotated_graph.pkl", "rb") as f:
    #     G = pickle.load(f)

    # print(f"✅ Loaded graph with {len(G.nodes)} nodes and {len(G.edges)} edges")

    # for node_id, data in G.nodes(data=True):
    #     summary = data.get("summary", "")
    #     if summary and summary.strip() != "":
    #         print(f"🧠 Node: {node_id}")
    #         print(f"Type: {data.get('type', 'unknown')}")
    #         print(f"Summary: {summary}")
    #         print("-" * 80)


    # exit()

    with open("annotated_graph.pkl", "rb") as f:
        G = pickle.load(f)

    
    
    async def test_annotate_graph():
        openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=600.0)

    repo_url = "https://github.com/ManimCommunity/manim.git"
    if not G:
        repo_path = clone_repo(repo_url)
        print(f"Cloned repo to {repo_path}")
        G = build_graph(repo_path)

        G = asyncio.run(annotate_graph_async(G, openai_client=openai_client))
        

        with open("annotated_graph.pkl", "wb") as f:
            pickle.dump(G, f)

        print("✅ Annotated graph saved to annotated_graph.pkl")







    # print(f"Built graph with {len(G.nodes())} nodes and {len(G.edges())} edges")

    # for node_id, data in G.nodes(data=True):
    #     # Combine all relevant text info
    #     node_type = data.get("type", "unknown")
    #     code = data.get("code", "")
    #     start_line = data.get("start_line", "")
    #     end_line = data.get("end_line", "")

    #     # Form textual input for embedding
    #     input_text = f"TYPE: {node_type}\nID: {node_id}\nCODE:\n{code}\nRANGE: {start_line}-{end_line}"

    #     print(f"node_type: {node_type}")
    #     print(f"code: {code}")
    #     print(f"node_id: {node_id}")
    #     print(f"\n\n\n")




    from backend.app.neo4j_client import Neo4jClient
    client = Neo4jClient(password="password") 
    # 3. Push graph to Neo4j
    # client.push_graph_to_neo4j(G, repo_id=repo_url)
    # client.close() 
    
    # node_embeddings = asyncio.run(embed_graph(G, openai_client=openai_client))

    # add_to_vector_store(node_embeddings, G, repo_url)



    from backend.app.vector_store import search_similar_nodes

    context_node_matches = search_similar_nodes("Where is the class QualityDict defined and what does it do?", 5, repo_url)
    # exit()

    # print(f"Context node matches:\n")
    # for node in context_node_matches:
    #     print(node)
    #     print(f"\n\n\n")
    
    # print(f"\n\n\n\n\n")

    print(f"Got {len(context_node_matches)} context node matches")
    for nn in context_node_matches:
        print(f"{nn['type']} {nn['node_id']}")
        print(f"\n\n\n")
    # exit()
    
    context_node_matches_ids = [r["node_id"] for r in context_node_matches]
    context_nodes = client.query_neo4j_neighbors(context_node_matches_ids, repo_url)

    print(f"Got {len(context_nodes)} context node neighbors (including the original context node matches) of the above {len(context_node_matches)} context node matches using query_neo4j_neighbors function.")
    # for nn in context_nodes:
    #     print(f"{nn['type']} {nn['node_id']}")
    #     print(f"\n\n\n")
    # exit()


    def print_node_matches_smart(context_node_matches):
        grouped = defaultdict(list)
        root_nodes = []

        for node in context_node_matches:
            node_type = node.get("type", "unknown")
            if node_type == "directory" or node.get("file_path", "") == "":
                root_nodes.append(node)
            else:
                grouped[node["file_path"]].append(node)

        print("\n\n=== 🗂️ Root / Directory Nodes ===\n")
        for node in root_nodes:
            print(f"🔹 ROOT/DIRECTORY NODE: {node['node_id']}")
            print(f"  - type: {node.get('type')}")
            print(f"  - score: {round(node.get('score', 0), 4)}")
            print()

        print("\n\n=== 📄 Code Snippets by File ===\n")
        for file_path, nodes in grouped.items():
            print(f"📄 File: {file_path}\n")
            for node in sorted(nodes, key=lambda n: n.get("start_line") or 0):
                ntype = node.get("type")
                nid = node.get("node_id")
                code = node.get("code", "").strip()
                start = node.get("start_line")
                end = node.get("end_line")
                header = f"[{ntype.capitalize()}] {nid}"
                if start and end and start != end:
                    header += f" (lines {start}–{end})"
                elif start:
                    header += f" (line {start})"

                print(f"  {header}")
                print("  " + "─" * (len(header) - 2))
                print("  " + code.replace("\n", "\n  "))
                print()
            print("\n")

    # print(f"DEBUGIN SHIT:\n")
    # print(f"{context_nodes[1]}")

    # for nn in context_nodes:
    #     print(f"{nn}")
    #     print(f"\n\n\n")
    
    # print_node_matches_smart(context_nodes)

    







# if __name__ == "__main___":
#     response = call_ask_endpoint("How does plagirism checker repo function logic works?", "https://github.com/Kalebu/Plagiarism-checker-Python.git")

#     print(f"\n\n\n\n")

#     print(f"Got {len(response['context'])} context nodes")
#     print(f"\n\n\n")
#     for context in response['context']:
#         print(context)
#         print(f"\n\n\n")







    # call_upload_repo_endpoint("https://github.com/Kalebu/Plagiarism-checker-Python.git")




# if __name__ == "__main__":
#     from backend.app.neo4j_client import Neo4jClient
#     import networkx as nx
#     G = nx.MultiDiGraph()
#     G.add_node("1", type="function", code="def hello_world(): print('Hello, World!')", start_line="1", end_line="2", file_path="test.py", repo_id="ayush-repo-123")
#     G.add_node("2", type="function", code="def goodbye_world(): print('Goodbye, World!')", start_line="3", end_line="4", file_path="test.py", repo_id="ayush-repo-123")
#     G.add_edge("1", "2", type="calls", repo_id="ayush-repo-123")
#     neo4j_client = Neo4jClient(password="password")
#     neo4j_client.push_graph_to_neo4j(G, repo_id="ayush-repo-123")

#     context = neo4j_client.query_neo4j_neighbors(["1"], repo_id="ayush-repo-123")
#     print(context)



 