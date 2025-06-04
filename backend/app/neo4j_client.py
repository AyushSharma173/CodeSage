# backend/app/neo4j_client.py
from __future__ import annotations

"""
Utility helpers to store a ``networkx`` graph inside Neo4j.

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
from typing import Any, Iterable, Tuple

import networkx as nx
from neo4j import GraphDatabase, Session, Driver
from typing import Optional, List

__all__ = [
    "Neo4jClient",
]

# ---------------------------------------------------------------------------
# Low-level Cypher templates -------------------------------------------------
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
_COUNT_RELS = "MATCH ()-[r:RELATION]-() RETURN count(r) AS count"


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
            tx.run(
                _CYPHER_MERGE_NODE,
                id=node_id,
                repo_id=repo_id,
                type=data.get("type", "unknown"),
                code=data.get("code", ""),
                file_path=data.get("file_path", ""),
                start_line=data.get("start_line", ""),
                end_line=data.get("end_line", ""),
                summary=data.get("summary", ""),
            )

    @staticmethod
    def _write_edge_chunk(tx: Session, chunk: Iterable[Tuple[str, str, dict]], repo_id: str):
        for src, dst, data in chunk:
            tx.run(
                _CYPHER_MERGE_REL,
                src=src,
                dst=dst,
                repo_id=repo_id,
                rel_type=data.get("type", "rel"),
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




    def print_all_nodes(self, results: dict):
        # ─── Print all nodes and their attributes/relationships ─────────────────────────
        for nid, entry in results.items():
            print(f"Node ID: {nid}")
            print(f"  type      : {entry.get('type', '')}")
            print(f"  file_path : {entry.get('file_path', '')}")
            print(f"  start_line: {entry.get('start_line', '')}")
            print(f"  end_line  : {entry.get('end_line', '')}")
            code_snippet = entry.get('code', '').strip()
            if code_snippet:
                print("  code      :")
                for line in code_snippet.splitlines():
                    print(f"    {line}")
            else:
                print("  code      : <no code>")

            rels = entry.get('relationships', [])
            if rels:
                print("  relationships:")
                for rel in rels:
                    print(f"    - ({rel['type']}) → {rel['target']}")
            else:
                print("  relationships: <none>")
            print("────────────────────────────────────────────────────────")
        # ────────────────────────────────────────────────────────────────────────────────

    


    def query_neo4j_neighbors(
        self,
        node_ids: list[str],
        repo_id: str,
        depth: int = 2,
        strategy: str = "default_bfs_all",
        edge_types: Optional[List[str]] = None,
        include_node_types: Optional[List[str]] = None,
        directed: bool = True,
        include_incoming: bool = True,
        include_outgoing: bool = True,
    ) -> list[dict]:
        """
        Return a list of node‐dicts, each containing its properties plus
        only those outgoing (and/or incoming) relationships that match `edge_types`.
        If include_node_types is provided, we only keep nodes whose `type` is in that list.

        The old `strategy`‐strings ("invokes_only", etc.) are still supported,
        but if `edge_types` is provided it will override them.
        """

        def _make_node_entry(rec_node) -> dict:
            nid = rec_node["id"]
            return {
                "node_id": nid,
                "type": rec_node.get("type", "unknown"),
                "code": rec_node.get("code", ""),
                "file_path": rec_node.get("file_path", ""),
                "start_line": rec_node.get("start_line"),
                "end_line": rec_node.get("end_line"),
                "relationships": [],
            }

        results: dict[str, dict] = {}
        seen_edges: set[tuple[str, str, str]] = set()

        # If the caller explicitly passed edge_types, it overrides `strategy`
        if edge_types:
            # Build a Cypher that follows only those `edge_types`
            edge_list = ", ".join(f"'{et}'" for et in edge_types)
            direction = "->" if directed else "-"
            hop_pattern = f"[r:RELATION*1..{depth}]{direction}"
            cypher = (
                f"MATCH path = (seed:CodeNode {{id:$seed, repo_id:$repo_id}})-{hop_pattern}(x)\n"
                f"WHERE ALL(n IN nodes(path) WHERE n.repo_id = $repo_id)\n"
                f"  AND ALL(e IN relationships(path) WHERE e.type IN [{edge_list}])\n"
                f"RETURN path"
            )
            for seed in node_ids:
                with self._driver.session() as sess:
                    for rec in sess.run(cypher, seed=seed, repo_id=repo_id):
                        path = rec["path"]
                        # Collect all nodes and edges that match
                        for node in path.nodes:
                            nid = node["id"]
                            ntype = node.get("type", "")
                            # If include_node_types is set, skip nodes not in that list
                            if include_node_types and ntype not in include_node_types:
                                continue
                            if nid not in results:
                                results[nid] = _make_node_entry(node)

                        for rel in path.relationships:
                            src = rel.start_node["id"]
                            dst = rel.end_node["id"]
                            rtype = rel.get("type", "")
                            if rtype not in edge_types:
                                continue
                            # Only add edges if both endpoints survive the node‐type filter
                            if src in results and dst in results:
                                edge_key = (src, dst, rtype)
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    results[src]["relationships"].append({"target": dst, "type": rtype})

            self.close()
            return list(results.values())

        # Otherwise, fall back to the original `strategy` logic:
        # ─────────────────────────────────────────────────────────────────────

        # 1) invokes_only
        if strategy == "invokes_only":
            cypher = """
            MATCH (n:CodeNode {id:$seed, repo_id:$repo_id})
            OPTIONAL MATCH (n)-[r1:RELATION {type:'invokes'}]->(m)
            OPTIONAL MATCH (m2)-[r2:RELATION {type:'invokes'}]->(n)
            WHERE (m.repo_id = $repo_id OR m2.repo_id = $repo_id)
            RETURN n, r1, m, r2, m2
            """
            for seed in node_ids:
                with self._driver.session() as sess:
                    for record in sess.run(cypher, seed=seed, repo_id=repo_id):
                        # Seed node
                        n = record["n"]
                        sid = n["id"]
                        # If node‐type filtering is requested, apply it here:
                        if include_node_types and n.get("type") not in include_node_types:
                            # skip adding this seed if it fails the type filter
                            continue
                        if sid not in results:
                            results[sid] = _make_node_entry(n)

                        # Outgoing invokes: n -> m
                        if record["r1"] and record["m"]:
                            m = record["m"]
                            mid = m["id"]
                            if include_node_types and m.get("type") not in include_node_types:
                                pass
                            else:
                                if mid not in results:
                                    results[mid] = _make_node_entry(m)
                                # Add edge n->m only if both sides survived node‐type filter
                                edge_key = (sid, mid, "invokes")
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    results[sid]["relationships"].append({"target": mid, "type": "invokes"})

                        # Incoming invokes: m2 -> n
                        if include_incoming and record["r2"] and record["m2"]:
                            m2 = record["m2"]
                            m2id = m2["id"]
                            if include_node_types and m2.get("type") not in include_node_types:
                                pass
                            else:
                                if m2id not in results:
                                    results[m2id] = _make_node_entry(m2)
                                edge_key = (m2id, sid, "invokes")
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    results[m2id]["relationships"].append({"target": sid, "type": "invokes"})

            self.close()
            return list(results.values())

        # 2) shallow_contains
        if strategy == "shallow_contains":
            cypher = """
            MATCH (n:CodeNode {id:$seed, repo_id:$repo_id})
            OPTIONAL MATCH (p)-[r:RELATION {type:'contains'}]->(n)
            WHERE p.repo_id = $repo_id
            RETURN n, r, p
            """
            for seed in node_ids:
                with self._driver.session() as sess:
                    for record in sess.run(cypher, seed=seed, repo_id=repo_id):
                        n = record["n"]
                        sid = n["id"]
                        if include_node_types and n.get("type") not in include_node_types:
                            continue
                        if sid not in results:
                            results[sid] = _make_node_entry(n)

                        if include_outgoing and record["r"] and record["p"]:
                            parent = record["p"]
                            pid = parent["id"]
                            if include_node_types and parent.get("type") not in include_node_types:
                                pass
                            else:
                                if pid not in results:
                                    results[pid] = _make_node_entry(parent)
                                edge_key = (pid, sid, "contains")
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    results[pid]["relationships"].append({"target": sid, "type": "contains"})

            self.close()
            return list(results.values())

        # 3) file_and_function_only
        if strategy == "file_and_function_only":
            cypher = f"""
            MATCH path = (n:CodeNode {{id:$seed, repo_id:$repo_id}})-[*1..{depth}]-(x)
            WHERE ALL(node IN nodes(path) WHERE node.repo_id = $repo_id)
            RETURN path
            """
            for seed in node_ids:
                with self._driver.session() as sess:
                    for rec in sess.run(cypher, seed=seed, repo_id=repo_id):
                        path = rec["path"]

                        # Node‐type filter to only keep nodes of type 'file' or 'function'
                        for node in path.nodes:
                            if node.get("type") in {"file", "function"}:
                                nid = node["id"]
                                if include_node_types and node.get("type") not in include_node_types:
                                    continue
                                if nid not in results:
                                    results[nid] = _make_node_entry(node)

                        # Collect edges between kept nodes
                        for rel in path.relationships:
                            src = rel.start_node["id"]
                            dst = rel.end_node["id"]
                            rtype = rel.get("type", "")
                            # Only add if both endpoints survived the node‐type filter
                            if src in results and dst in results:
                                edge_key = (src, dst, rtype)
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    results[src]["relationships"].append({"target": dst, "type": rtype})

            self.close()
            return list(results.values())

        # 4) deep_logic_chain
        if strategy == "deep_logic_chain":
            # Replace 3 hops with the user‐provided `depth`, if desired:
            cypher = f"""
            MATCH path = (n:CodeNode {{id:$seed, repo_id:$repo_id}})
            -[r:RELATION*1..{depth}]->(m)
            WHERE ALL(x IN nodes(path) WHERE x.repo_id = $repo_id)
            AND ALL(relEdge IN relationships(path) WHERE relEdge.type IN ['invokes','inherits'])
            RETURN path
            """
            for seed in node_ids:
                with self._driver.session() as sess:
                    for rec in sess.run(cypher, seed=seed, repo_id=repo_id):
                        path = rec["path"]

                        # Keep every node on this path (unless a node‐type filter rejects it)
                        for node in path.nodes:
                            nid = node["id"]
                            if include_node_types and node.get("type") not in include_node_types:
                                continue
                            if nid not in results:
                                results[nid] = _make_node_entry(node)

                        # Only add 'invokes' or 'inherits' edges
                        for rel in path.relationships:
                            src = rel.start_node["id"]
                            dst = rel.end_node["id"]
                            rtype = rel.get("type", "")
                            if rtype in {"invokes", "inherits"}:
                                # only if both endpoints survived the node‐type filter
                                if src in results and dst in results:
                                    edge_key = (src, dst, rtype)
                                    if edge_key not in seen_edges:
                                        seen_edges.add(edge_key)
                                        results[src]["relationships"].append({"target": dst, "type": rtype})

            self.close()
            return list(results.values())

        # 5) class_hierarchy
        if strategy == "class_hierarchy":
            cypher = f"""
            MATCH path = (n:CodeNode {{id:$seed, repo_id:$repo_id}})
            -[r:RELATION*1..{depth}]->(m)
            WHERE ALL(x IN nodes(path) WHERE x.repo_id = $repo_id)
            AND ALL(relEdge IN relationships(path) WHERE relEdge.type = 'inherits')
            RETURN path
            """
            for seed in node_ids:
                with self._driver.session() as sess:
                    for rec in sess.run(cypher, seed=seed, repo_id=repo_id):
                        path = rec["path"]

                        for node in path.nodes:
                            nid = node["id"]
                            if include_node_types and node.get("type") not in include_node_types:
                                continue
                            if nid not in results:
                                results[nid] = _make_node_entry(node)

                        for rel in path.relationships:
                            src = rel.start_node["id"]
                            dst = rel.end_node["id"]
                            rtype = rel.get("type", "")
                            if rtype == "inherits" and src in results and dst in results:
                                edge_key = (src, dst, rtype)
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    results[src]["relationships"].append({"target": dst, "type": rtype})

            self.close()
            return list(results.values())

        # 6) default_bfs_all
        # (fall back to a plain undirected BFS of up to `depth`, any relationship)
        cypher = f"""
        MATCH path = (n:CodeNode {{id:$seed, repo_id:$repo_id}})-[*1..{depth}]-(x)
        WHERE ALL(node IN nodes(path) WHERE node.repo_id = $repo_id)
        RETURN path
        """
        for seed in node_ids:
            with self._driver.session() as sess:
                for rec in sess.run(cypher, seed=seed, repo_id=repo_id):
                    path = rec["path"]

                    # Include every node (unless node‐type filtering rejects it)
                    for node in path.nodes:
                        nid = node["id"]
                        if include_node_types and node.get("type") not in include_node_types:
                            continue
                        if nid not in results:
                            results[nid] = _make_node_entry(node)

                    # Include every edge between kept nodes
                    for rel in path.relationships:
                        src = rel.start_node["id"]
                        dst = rel.end_node["id"]
                        rtype = rel.get("type", "")
                        if src in results and dst in results:
                            edge_key = (src, dst, rtype)
                            if edge_key not in seen_edges:
                                seen_edges.add(edge_key)
                                results[src]["relationships"].append({"target": dst, "type": rtype})

        self.close()
        return list(results.values())


