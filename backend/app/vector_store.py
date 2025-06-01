# backend/app/vector_store.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, SearchRequest
from qdrant_client.models import DeleteVectors, DeleteVectorsOperation
from qdrant_client.models import PayloadSchemaType
import hashlib
import networkx as nx
from openai import OpenAI
import os
from dotenv import load_dotenv
import json
# Load environment variables
load_dotenv()

COLLECTION_NAME = "codebase-vectors"

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Qdrant client
client = QdrantClient(
    url="https://a832760d-f7f1-4550-a760-33ade04f385a.us-west-2-0.aws.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.L_4bUSn79dxhGT4a7UKBrMtCU8imk9oDNoikWVSaEsg"
)

# Ensure collection exists
def init_collection(embedding_dim: int = 1536):
    print(f"Initializing collection")
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
        )
    # 2) Create a keyword index on "repo_id"
    #    If the index already exists, Qdrant will ignore and do nothing.
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="repo_id",
        field_schema=PayloadSchemaType.KEYWORD
    )




def _hash_id(text: str) -> int:
    """Creates a stable integer ID from a string using SHA1."""
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % (10**16)

def _get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """Get embedding for a text using OpenAI's API."""
    response = openai_client.embeddings.create(
        input=text,
        model=model
    )
    return response.data[0].embedding


def extract_file_path(node_id: str, node_type: str) -> str:
    if node_type in ("function", "class"):
        return node_id.split(":", 1)[0]
    elif node_type == "file":
        return node_id
    else:
        # probably a directory, return empty or "/" as fallback
        return ""


def chunked(iterable, size=256):
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


from tqdm import tqdm
# Main function to upload vectors
def add_to_vector_store(embeddings: dict[str, list[float]], graph: nx.MultiDiGraph, repo_id: str):
    """
    embeddings: Dict of node_id -> embedding vector
    graph: The networkx graph containing node information
    """
    print(f"Inside add_to_vector_store function")

    init_collection(embedding_dim=len(next(iter(embeddings.values()))))

    points = []
    for node_id, vector in embeddings.items():
        node_data = graph.nodes[node_id]

        file_path = extract_file_path(node_id, node_data.get("type", "unknown"))

        payload = {
            "node_id": node_id,
            "type": node_data.get("type", "unknown"),
            "summary": node_data.get("summary", ""),
            "code": node_data.get("code", ""),
            "start_line": node_data.get("start_line", ""),
            "end_line": node_data.get("end_line", ""),
            "file_path": file_path,
            "repo_id": repo_id
        }

        if "relationships" in node_data:
            payload["relationships"] = node_data["relationships"]

        points.append(
            PointStruct(
                id=_hash_id(node_id),
                vector=vector,
                payload=payload
            )
        )

        # (Optional) debug print
        print(f"✅ Prepared node_id: {node_id} | type: {node_data.get('type', 'unknown')}")

    print(f"🚀 Total points to upsert: {len(points)}")

    for batch in tqdm(chunked(points, size=256), desc="🔄 Upserting to Qdrant"):
        client.upsert(
            collection_name=COLLECTION_NAME,
            wait=True,
            points=batch
        )

    print("✅ All points successfully upserted.")





from qdrant_client.models import Filter, FieldCondition, MatchValue

def search_similar_nodes(query: str, top_k: int = 5, repo_id: str = "") -> list[dict]:
    """
    Search for nodes similar to the query text, scoped to a specific repo_id.
    """
    print(f"Searching for similar nodes to {query} in repo {repo_id}")
    # Get embedding for the query
    query_embedding = _get_embedding(query)

    # Define a filter to only include points from the given repo
    repo_filter = Filter(
        must=[
            FieldCondition(
                key="repo_id",
                match=MatchValue(value=repo_id)
            )
        ]
    )

    # Perform filtered vector search
    search_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=top_k,
        query_filter=repo_filter,  # <- filter by repo
        with_payload=True          # include payload in result
    )

    # print(f"search_results: {search_results}")

    # Parse results
    results = []
    for point in search_results.points:
        payload = point.payload
        results.append({
            "node_id": payload.get("node_id"),
            "summary": payload.get("summary"),
            "repo_id": payload.get("repo_id"),
            "type": payload.get("type"),
            "code": payload.get("code"),
            "file_path": payload.get("file_path"),
            "start_line": payload.get("start_line"),
            "end_line": payload.get("end_line"),
            "score": point.score
        })

    # print(f"results: {results}")

    return results



def delete_vectors_for_nodes(node_ids: list[str]):
    """
    Deletes the vector(s) from the given node_ids (but keeps the point & payload).
    
    Args:
        node_ids: List of node_id strings whose vectors should be deleted.
    """
    point_ids = [_hash_id(node_id) for node_id in node_ids]
    
    print(f"Deleting vectors for {len(point_ids)} points from '{COLLECTION_NAME}'...")

    # Delete all vectors for each point
    for point_id in point_ids:
        client.delete_vectors(
            collection_name=COLLECTION_NAME,
            points=[point_id],
            vectors=None  # The default vector name in our collection
        )

    print("Deletion completed.")




from qdrant_client.models import DeleteVectorsOperation, PayloadSelectorInclude

def delete_all_vectors():
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=10000000,
        with_vectors=True,
        with_payload=False
    )

    print(f"🧠 Found {len(points)} points")

    point_ids = [p.id for p in points]
    print(f"💀 Point IDs: {point_ids}")

    for pid in point_ids:
        print(f"🧹 Deleting vectors from point: {pid}")
        client.delete_vectors(
            collection_name=COLLECTION_NAME,
            points=[pid],
            vectors=[""]
        )
    client.delete_collection(COLLECTION_NAME)

    print("✅ All vectors deleted.")





from qdrant_client.models import Filter, FieldCondition, MatchValue

from qdrant_client.models import Filter, FieldCondition, MatchValue

def delete_vectors_for_repo(repo_id: str):
    # Step 1: Find all point IDs with this repo_id
    point_ids = []
    offset = None

    repo_filter = Filter(
        must=[FieldCondition(key="repo_id", match=MatchValue(value=repo_id))]
    )

    while True:
        result, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=repo_filter,
            limit=100,
            with_payload=False,
            with_vectors=False,
            offset=offset,
        )

        point_ids.extend([p.id for p in result])

        if offset is None:
            break

    print(f"Found {len(point_ids)} points to delete vectors from")

    # Step 2: Delete vectors for those points
    if point_ids:
        client.delete_vectors(
            collection_name=COLLECTION_NAME,
            points=point_ids,
            vectors=[""]  # Deletes all vectors for these points
        )
        print("✅ Vectors deleted.")
    else:
        print("⚠️ No points found for given repo_id.")



from qdrant_client.models import ScrollRequest

def count_vectors_in_collection(repo_id: str) -> int:
    total_vectors = 0
    offset = None

    # Add filter for specific repo_id
    repo_filter = Filter(
        must=[
            FieldCondition(
                key="repo_id",
                match=MatchValue(value=repo_id)
            )
        ]
    )

    while True:
        result, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            with_vectors=True,
            with_payload=False,
            offset=offset,
            limit=100,  # adjust batch size as needed
            scroll_filter=repo_filter
        )

        for point in result:
            if point.vector:
                # Count single vector or multiple named vectors
                if isinstance(point.vector, dict):
                    total_vectors += len(point.vector)
                else:
                    total_vectors += 1

        if next_offset is None:
            break
        offset = next_offset

    print(f"✅ Total vectors in collection '{COLLECTION_NAME}' for repo '{repo_id}': {total_vectors}")
    return total_vectors






def debug_check_vectors_exist():


    repo_id = "https://github.com/unslothai/unsloth.git"
    # Add filter for specific repo_id
    repo_filter = Filter(
        must=[
            FieldCondition(
                key="repo_id",
                match=MatchValue(value=repo_id)
            )
        ]
    )


    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=5,
        with_vectors=True,
        with_payload=True,
        scroll_filter=repo_filter
    )
    if not points:
        print("❌ No points with vectors found in the collection.")
    else:
        print(f"✅ Found {len(points)} point(s) with vectors. Example:")
        for pt in points:
            print(f"- ID: {pt.id}, Node ID: {pt.payload.get('node_id')}, File: {pt.payload.get('file_path')}")


def inspect_query_embedding(query: str):
    emb = _get_embedding(query)
    print(f"🔍 Query: '{query}'")
    print(f"🧬 Embedding dim: {len(emb)}")
    print(f"🧬 First few dims: {emb[:5]}")



def debug_query_by_existing_vector():
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=10,
        with_vectors=False,
        with_payload=True
    )
    if not points:
        print("No points found to extract vector from.")
        return
    for point in points[:1]:
        print(point)
    # test_vec = points[0].vector
    # vec = points[0].vector
    # print(f"vec: {vec}")
    # test_vec = vec["default"] if isinstance(vec, dict) else vec

    # print("Running self-query with vector from existing point...")

    # result = client.query_points(
    #     collection_name=COLLECTION_NAME,
    #     query=test_vec,
    #     limit=5,
    #     with_payload=True
    # )

    # for pt in result.points:
    #     print(f"- ID: {pt.id}, Score: {pt.score}, Node ID: {pt.payload.get('node_id')}")



def debug_vector_search(query: str, top_k: int = 5):
    print(f"🔍 Running raw vector search for query: '{query}'")
    
    query_embedding = _get_embedding(query)
    print(f"query_embedding: {query_embedding}")

    search_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=top_k,
        with_payload=True,
        
    )

    print(f"search_results: {search_results}")
    if not search_results.points:
        print("❌ No points matched the query.")
    else:
        print(f"✅ Found {len(search_results.points)} points:")
        for point in search_results.points:
            print(f"- ID: {point.id}, Score: {point.score:.4f}, Node: {point.payload.get('node_id')}, Repo: {point.payload.get('repo_id')}")



if __name__ == "__main__":
    # debug_check_vectors_exist()
    # inspect_query_embedding("utility functions in _utils.py")
    # debug_query_by_existing_vector()

    # debug_vector_search("utility functions in _utils.py", 10)



    # delete_vectors_for_repo(repo_id="ayush-repo-123")
    # exit()
    # count_vectors_in_collection(repo_id="ayush-repo-123")
    # exit()
    delete_all_vectors()
    from neo4j_client import Neo4jClient
    neo4j_client = Neo4jClient(password="password")
    neo4j_client.wipe_entire_database()
    exit()

    # delete_vectors_for_nodes(["1", "2"])
    # exit()
    # Test the vector store
    from embedder import embed_graph
    G = nx.MultiDiGraph()
    G.add_node("1", 
               type="function", 
               code="def hello_world(): print('Hello, World!')", 
               start_line="1", 
               end_line="2",
               file_path="test.py",
               repo_id="ayush-repo-123")
    G.add_node("2", 
               type="function", 
               code="def goodbye_world(): print('Goodbye, World!')", 
               start_line="3", 
               end_line="4",
               file_path="test.py",
               repo_id="ayush-repo-123")
    G.add_edge("1", "2", type="calls", repo_id="ayush-repo-123")

    from neo4j_client import Neo4jClient
    neo4j_client = Neo4jClient(password="password")
    neo4j_client.push_graph_to_neo4j(G, repo_id="ayush-repo-123")

    embeddings = embed_graph(G)
    add_to_vector_store(embeddings, G, repo_id="ayush-repo-123")
    
    # Test the search function
    query = "function that prints hello"
    results = search_similar_nodes(query, repo_id="ayush-repo-123")
    print(f"\nSearch results for query: '{query}'")
    for result in results:
        print(f"\nNode ID: {result['node_id']}")
        print(f"Type: {result['type']}")
        print(f"File: {result['file_path']}")
        print(f"Lines: {result['start_line']}-{result['end_line']}")
        print(f"Code: {result['code']}")
        print(f"Similarity Score: {result['score']:.4f}")
        print("---")






