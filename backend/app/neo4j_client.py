# backend/app/neo4j_client.py
from __future__ import annotations

"""Utility helpers to store a ``networkx`` graph inside Neo4j.

Public API
==========
``Neo4jClient`` – thin wrapper around the Bolt driver
-----------------------------------------------------

    >>> from backend.graph_builder import build_graph
    >>> from backend.neo4j_client import Neo4jClient
    >>> 
    >>> g = build_graph("/tmp/repo", verbose=False)
    >>> client = Neo4jClient(password="secret")          # uri & user default
    >>> client.push_graph_to_neo4j(g, repo_id="my-repo-1", batch_size=500)
    >>> print(client.count_nodes(), client.count_rels())
    >>> client.close()

The module does **not** depend on FastAPI – you can import it directly in your
routes or background tasks.
"""

import os
from typing import Iterable, Tuple, Any

import networkx as nx
from neo4j import GraphDatabase, Session, Driver
from neo4j.exceptions import Neo4jError

__all__ = [
    "Neo4jClient",
]

# ---------------------------------------------------------------------------
# Low‑level Cypher templates -------------------------------------------------
# ---------------------------------------------------------------------------

_CYPHER_MERGE_NODE = """
MERGE (n:CodeNode {id: $id})
SET 
    n.type = $type,
    n.code = $code,
    n.file_path = $file_path,
    n.start_line = $start_line,
    n.end_line = $end_line,
    n.repo_id = $repo_id,
    n.summary = $summary
"""


_CYPHER_MERGE_REL = """
MATCH (a:CodeNode {id: $src, repo_id: $repo_id})
MATCH (b:CodeNode {id: $dst, repo_id: $repo_id})
MERGE (a)-[r:RELATION {type: $rel_type}]->(b)
"""

_COUNT_NODES = "MATCH (n:CodeNode) RETURN count(n) AS count"
_COUNT_RELS  = "MATCH ()-[r:RELATION]-() RETURN count(r) AS count"


# ---------------------------------------------------------------------------
# Helper --------------------------------------------------------------------
# ---------------------------------------------------------------------------

def _chunk(iterable: Iterable[Any], size: int):
    """Yield *size*-sized chunks from *iterable*."""
    buff: list[Any] = []
    for item in iterable:
        buff.append(item)
        if len(buff) == size:
            yield buff
            buff = []
    if buff:
        yield buff


# ---------------------------------------------------------------------------
# Public client --------------------------------------------------------------
# ---------------------------------------------------------------------------

class Neo4jClient:
    """Thin convenience wrapper around the official neo4j‐python driver."""

    def __init__(
        self,
        database: str = "neo4j",
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        **driver_kwargs,
    ) -> None:
        uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = user or os.getenv("NEO4J_USER", "neo4j")
        password = password or os.getenv("NEO4J_PASSWORD", "neo4j")

        self.database = database
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password), **driver_kwargs)
        self._driver.verify_connectivity()

    def close(self) -> None:
        self._driver.close()

    def _session(self):
        return self._driver.session(database=self.database)

    def count_nodes(self) -> int:
        with self._driver.session() as sess:
            return sess.run(_COUNT_NODES).single()["count"]

    def count_rels(self) -> int:
        with self._driver.session() as sess:
            return sess.run(_COUNT_RELS).single()["count"]

    def push_graph_to_neo4j(
        self,
        graph: nx.MultiDiGraph,
        *,
        repo_id: str,
        batch_size: int = 1000,
        clear_first: bool = False,
    ) -> None:
        """Store *graph* into Neo4j, namespaced by `repo_id`."""
        if clear_first:
            self._wipe_database(repo_id=repo_id)

        with self._driver.session() as sess:
            for chunk in _chunk(graph.nodes(data=True), batch_size):
                sess.execute_write(self._write_node_chunk, chunk, repo_id)
            for chunk in _chunk(graph.edges(data=True), batch_size):
                sess.execute_write(self._write_edge_chunk, chunk, repo_id)


    @staticmethod
    def _write_node_chunk(tx: Session, chunk: Iterable[Tuple[str, dict]], repo_id: str):
        for node_id, data in chunk:
            tx.run(_CYPHER_MERGE_NODE,
                id=node_id,
                repo_id=repo_id,
                type=data.get("type", "unknown"),
                code=data.get("code", ""),
                file_path=data.get("file_path", ""),
                start_line=data.get("start_line", ""),
                end_line=data.get("end_line", ""),
                summary=data.get("summary", "")
                )
            

    @staticmethod
    def _write_edge_chunk(tx: Session, chunk: Iterable[Tuple[str, str, dict]], repo_id: str):
        for src, dst, data in chunk:
            tx.run(
                _CYPHER_MERGE_REL,
                src=src,
                dst=dst,
                repo_id=repo_id,
                rel_type=data.get("type", "rel")
            )

    def get_neighbors(self, node_id: str, repo_id: str, depth: int = 2):
        cypher = (
            f"MATCH path = (n:CodeNode {{id: $id, repo_id: $repo_id}})-[*1..{depth}]-() "
            f"WHERE ALL(x IN nodes(path) WHERE x.repo_id = $repo_id) "
            f"RETURN path"
        )

        with self._driver.session() as sess:
            for record in sess.run(cypher, id=node_id, repo_id=repo_id):
                yield record["path"]

    def _wipe_database(self, repo_id: str):
        with self._session() as sess:
            sess.run("MATCH ()-[r:RELATION]-() WHERE r.repo_id = $repo_id DELETE r", repo_id=repo_id)
            sess.run("MATCH (n:CodeNode {repo_id: $repo_id}) DELETE n", repo_id=repo_id)

    def wipe_entire_database(self):
        """Dangerous: Completely deletes ALL nodes and relationships from the database."""
        with self._session() as sess:
            sess.run("MATCH ()-[r]-() DELETE r")
            sess.run("MATCH (n) DELETE n")



    def query_neo4j_neighbors(self, node_ids: list[str], repo_id: str, depth: int = 2, strategy: str = 'default_bfs_all') -> list[dict]:
        context_nodes = {}
        rel_filters = None
        node_type_filters = None
        max_depth = depth

        # ===== Strategy Configurations =====
        if strategy == "invokes_only":
            rel_filters = {"invokes"}
        elif strategy == "shallow_contains":
            rel_filters = {"contains"}
            max_depth = 1
        elif strategy == "file_and_function_only":
            node_type_filters = {"file", "function"}
        elif strategy == "deep_logic_chain":
            rel_filters = {"invokes", "inherits"}
            max_depth = 3
        elif strategy == "class_hierarchy":
            rel_filters = {"inherits"}
            max_depth = 2
        # More strategies can be defined here...

        for node_id in node_ids:
            for path in self.get_neighbors(node_id, repo_id=repo_id, depth=max_depth):
                for node in path.nodes:
                    nid = node["id"]
                    if nid not in context_nodes:
                        if node_type_filters and node.get("type") not in node_type_filters:
                            continue
                        context_nodes[nid] = {
                            "node_id": nid,
                            "type": node.get("type", "unknown"),
                            "code": node.get("code", ""),
                            "file_path": node.get("file_path", ""),
                            "start_line": node.get("start_line", ""),
                            "end_line": node.get("end_line", ""),
                        }

                for rel in path.relationships:
                    src = rel.start_node["id"]
                    dst = rel.end_node["id"]
                    rel_type = rel.get("type", "rel")
                    if rel_filters and rel_type not in rel_filters:
                        continue
                    context_nodes[src].setdefault("relationships", []).append(
                        {"target": dst, "type": rel_type}
                    )

        self.close()
        return list(context_nodes.values())
    