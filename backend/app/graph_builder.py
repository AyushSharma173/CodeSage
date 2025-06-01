# ── backend/graph_builder.py ──────────────────────────────────────────────────
"""
Build a static dependency graph for a Python code‑base.

The graph is a `networkx.MultiDiGraph` whose nodes and edges carry rich
metadata:

    • directory  ───contains──▶ file
    • file       ───contains──▶ class / function
    • class      ───invokes────▶ class / function     (calls inside __init__)
    • function   ───invokes────▶ class / function     (calls inside body)
    • class      ───inherits───▶ class
    • *, file    ───imports────▶ file | class | function

The logic is adapted from the monolithic script you shared but trimmed for use
as a library inside a web‑backend.
"""
from __future__ import annotations

import ast
import os
import re
from collections import defaultdict
from typing import List, Dict, Tuple

import networkx as nx

# ────────────────  Public constants  ──────────────────────────────────────────
VERSION = "v2.3"

NODE_TYPE_DIRECTORY = "directory"
NODE_TYPE_FILE       = "file"
NODE_TYPE_CLASS      = "class"
NODE_TYPE_FUNCTION   = "function"

EDGE_TYPE_CONTAINS  = "contains"
EDGE_TYPE_INHERITS  = "inherits"
EDGE_TYPE_INVOKES   = "invokes"
EDGE_TYPE_IMPORTS   = "imports"

VALID_NODE_TYPES = [
    NODE_TYPE_DIRECTORY, NODE_TYPE_FILE, NODE_TYPE_CLASS, NODE_TYPE_FUNCTION
]
VALID_EDGE_TYPES = [
    EDGE_TYPE_CONTAINS, EDGE_TYPE_INHERITS, EDGE_TYPE_INVOKES, EDGE_TYPE_IMPORTS
]

# folders you never want indexed (virtual envs, git internals, caches, etc.)
SKIP_DIRS = {
    ".git", ".github", ".mypy_cache", "__pycache__", ".idea", "venv", "env",
    "assets", "evaluation", "plots", "repo_index", "scripts", "ven"
}
GENERIC_FILE_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".md", ".txt", ".ipynb", ".json", ".yaml", ".yml", ".cfg", ".toml")

# ──────────────────────────────────────────────────────────────────────────────


# ==========  helpers ==========================================================
def _is_skip_dir(path_part: str) -> bool:
    return any(skip in path_part.split(os.sep) for skip in SKIP_DIRS)


def _read_tree(path: str) -> ast.AST | None:
    try:
        with open(path, "r", encoding="utf‑8") as fh:
            return ast.parse(fh.read(), filename=path)
    except (UnicodeDecodeError, SyntaxError):
        return None


class _CodeAnalyzer(ast.NodeVisitor):
    """
    Walk a module and collect:
        * classes
        * top‑level functions
        * nested methods (but skip __init__)
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.results: List[Dict] = []
        self._name_stack: List[str] = []
        self._type_stack: List[str] = []

    # ── visitor overrides ──────────────────────────────────────────────────
    def visit_ClassDef(self, node: ast.ClassDef):
        full = ".".join(self._name_stack + [node.name])
        self.results.append({
            "name": full,
            "type": NODE_TYPE_CLASS,
            "code": ast.get_source_segment(open(self.filename).read(), node),
            "start": node.lineno,
            "end": node.end_lineno,
        })
        self._name_stack.append(node.name)
        self._type_stack.append(NODE_TYPE_CLASS)
        self.generic_visit(node)
        self._type_stack.pop()
        self._name_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self._type_stack and self._type_stack[-1] == NODE_TYPE_CLASS and node.name == "__init__":
            return
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_func(node)

    # ── private helpers ────────────────────────────────────────────────────
    def _visit_func(self, node: ast.AST):
        full = ".".join(self._name_stack + [node.name])
        self.results.append({
            "name": full,
            "type": NODE_TYPE_FUNCTION,
            "code": ast.get_source_segment(open(self.filename).read(), node),
            "start": node.lineno,
            "end": node.end_lineno,
        })
        self._name_stack.append(node.name)
        self._type_stack.append(NODE_TYPE_FUNCTION)
        self.generic_visit(node)
        self._type_stack.pop()
        self._name_stack.pop()


def _analyze_file(path: str) -> List[Dict]:
    tree = _read_tree(path)
    if tree is None:
        return []
    analyzer = _CodeAnalyzer(path)
    analyzer.visit(tree)
    return analyzer.results


def _resolve_module(module: str, repo_root: str) -> str | None:
    """
    Turn 'a.b.c' into /repo_root/a/b/c.py or .../a/b/c/__init__.py
    """
    candidate = os.path.join(repo_root, *module.split(".")) + ".py"
    if os.path.isfile(candidate):
        return candidate
    init_candidate = os.path.join(repo_root, *module.split("."), "__init__.py")
    return init_candidate if os.path.isfile(init_candidate) else None


def _find_imports(path: str, repo_root: str, subtree: ast.AST | None = None):
    """Return structured import statements for a file or AST subtree."""
    if subtree is None:
        subtree = _read_tree(path)
        if subtree is None:
            return []

    nodes = ast.walk(subtree) if subtree is not None else []
    result = []
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append({"kind": "import", "module": alias.name, "alias": alias.asname})
        elif isinstance(node, ast.ImportFrom):
            entities = [{"name": a.name, "alias": a.asname} for a in node.names]
            # compute fully qualified module name for relative import
            if node.level and node.level > 0:
                rel = os.path.relpath(path, repo_root)
                parts = rel.split(os.sep)[:-node.level]
                module = ".".join(parts + ([] if node.module is None else [node.module]))
            else:
                module = node.module or ""
            result.append({"kind": "from", "module": module, "entities": entities})
    return result


# ==========  public API =======================================================
def build_graph(
    repo_path: str,
    *,
    skip_tests: bool = True,
    fuzzy_search: bool = True,
    follow_relative_imports: bool = False,
    verbose: bool = True,
) -> nx.MultiDiGraph:
    """
    Crawl *repo_path* and build a dependency graph.

    Parameters
    ----------
    repo_path : str
        Folder containing the Python project.
    skip_tests : bool
        Exclude files/folders whose path starts with "test".
    fuzzy_search : bool
        When resolving invokes/imports, match by suffix (may yield multiple targets).
    follow_relative_imports : bool
        If True, walk through `from .foo import Bar` even when pointer is outside repo.
    verbose : bool
        Print progress to stdout.

    Returns
    -------
    networkx.MultiDiGraph
    """
    G = nx.MultiDiGraph()
    G.add_node("/", type=NODE_TYPE_DIRECTORY, file_path="/")




    # ── step 0: special README node ──────────────────────────────────────────
    readme_candidates = ["README.md", "readme.md", "README.txt", "readme.txt", "README"]
    for candidate in readme_candidates:
        readme_path = os.path.join(repo_path, candidate)
        if os.path.isfile(readme_path):
            with open(readme_path, "r", encoding="utf-8", errors="ignore") as fh:
                readme_content = fh.read()
            G.add_node(
                "__README__",
                type="readme",
                file_path=candidate,
                code=readme_content.strip()
            )
            G.add_edge("/", "__README__", type=EDGE_TYPE_CONTAINS)
            if verbose:
                print(f"[+] Found README: {candidate}")
            break  # Stop at the first valid README




    file_nodes: Dict[str, str] = {}       # repo‑relative → absolute path
    dir_stack, dir_included = [], []      # helpers for pruning empty dirs

    # ── step 1: index all .py files ────────────────────────────────────────
    for root, _dirs, files in os.walk(repo_path):
        if _is_skip_dir(root):
            continue
        rel_dir = os.path.relpath(root, repo_path) or "/"
        if verbose:
            print(f"[+] Scanning {rel_dir}")

        # register directory node
        if rel_dir != "/" and not G.has_node(rel_dir):
            parent = os.path.dirname(rel_dir) or "/"
            G.add_node(rel_dir, type=NODE_TYPE_DIRECTORY, file_path=rel_dir)
            G.add_edge(parent, rel_dir, type=EDGE_TYPE_CONTAINS)

        # pop dir stack on ascent
        while dir_stack and not rel_dir.startswith(dir_stack[-1]):
            if not dir_included[-1]:
                G.remove_node(dir_stack[-1])
            dir_stack.pop(); dir_included.pop()

        if rel_dir != "/":
            dir_stack.append(rel_dir)
            dir_included.append(False)


        for fname in files:            
            # Handle different file types
            if fname.endswith(".py"):
                # === Python file: parse code and inner nodes ===
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, repo_path)

                if verbose:
                    print(f"   └─ {rel_path}")

                with open(abs_path, "r", encoding="utf‑8") as fh:
                    code = fh.read()
                G.add_node(rel_path, type=NODE_TYPE_FILE, file_path=rel_path)
                G.add_edge(rel_dir, rel_path, type=EDGE_TYPE_CONTAINS)
                file_nodes[rel_path] = abs_path

                for meta in _analyze_file(abs_path):
                    nid = f"{rel_path}:{meta['name']}"
                    G.add_node(
                        nid,
                        type=meta["type"],
                        code=meta["code"],
                        start_line=meta["start"],
                        end_line=meta["end"],
                        file_path=rel_path
                    )
                    if "." in meta["name"]:
                        parent_name = ".".join(meta["name"].split(".")[:-1])
                        parent_nid = f"{rel_path}:{parent_name}"
                    else:
                        parent_nid = rel_path
                    G.add_edge(parent_nid, nid, type=EDGE_TYPE_CONTAINS)
                continue  # ✅ done handling .py files

            # === Generic file types (no AST parsing) ===
            if fname.lower().endswith(GENERIC_FILE_SUFFIXES):
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, repo_path)
                if verbose:
                    print(f"   └─ [GENERIC] {rel_path}")

                G.add_node(rel_path, type="generic_file", file_path=rel_path)
                G.add_edge(rel_dir, rel_path, type=EDGE_TYPE_CONTAINS)
                continue

            # # === Skip all other files (e.g., images, binaries) ===
            # continue

    # ── step 2: imports between files/classes/functions ────────────────────
    for rel_path, abs_path in file_nodes.items():
        for imp in _find_imports(abs_path, repo_path):
            if imp["kind"] == "import":
                tgt_path = _resolve_module(imp["module"], repo_path)
                if tgt_path:
                    tgt_rel = os.path.relpath(tgt_path, repo_path)
                    if G.has_node(tgt_rel):
                        G.add_edge(rel_path, tgt_rel, type=EDGE_TYPE_IMPORTS, alias=imp["alias"])
            else:  # from ... import ...
                if len(imp["entities"]) == 1 and imp["entities"][0]["name"] == "*":
                    tgt_path = _resolve_module(imp["module"], repo_path)
                    if tgt_path:
                        tgt_rel = os.path.relpath(tgt_path, repo_path)
                        if G.has_node(tgt_rel):
                            G.add_edge(rel_path, tgt_rel, type=EDGE_TYPE_IMPORTS)
                    continue
                for ent in imp["entities"]:
                    ent_mod = f"{imp['module']}.{ent['name']}"
                    ent_path = _resolve_module(ent_mod, repo_path)
                    if ent_path:
                        tgt_rel = os.path.relpath(ent_path, repo_path)
                        if G.has_node(tgt_rel):
                            G.add_edge(rel_path, tgt_rel, type=EDGE_TYPE_IMPORTS)
                    else:
                        maybe_mod = _resolve_module(imp["module"], repo_path)
                        if maybe_mod:
                            base_rel = os.path.relpath(maybe_mod, repo_path)
                            node_id = f"{base_rel}:{ent['name']}"
                            if G.has_node(node_id):
                                G.add_edge(rel_path, node_id, type=EDGE_TYPE_IMPORTS)


    # ── step 3: intra‑file invokes / inherits edges ────────────────────────
    for rel_path, abs_path in file_nodes.items():
        tree = _read_tree(abs_path)
        if tree is None:
            continue

        # Walk the AST of this file
        for node in ast.walk(tree):
            # 1) Class inheritance edges
            if isinstance(node, ast.ClassDef):
                class_nid = f"{rel_path}:{node.name}"
                # for each base class in class definition
                for base in node.bases:
                    # get simple name of the base
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    else:
                        continue
                    target_nid = f"{rel_path}:{base_name}"
                    if G.has_node(target_nid):
                        G.add_edge(
                            class_nid,
                            target_nid,
                            type=EDGE_TYPE_INHERITS
                        )

            # 2) Function / method invoke edges
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_nid = f"{rel_path}:{node.name}"
                # look for all Call nodes inside this function
                for call in ast.walk(node):
                    if not isinstance(call, ast.Call):
                        continue

                    # extract the called function name
                    if isinstance(call.func, ast.Name):
                        called = call.func.id
                    elif isinstance(call.func, ast.Attribute):
                        called = call.func.attr
                    else:
                        continue

                    target_nid = f"{rel_path}:{called}"
                    if G.has_node(target_nid):
                        G.add_edge(
                            func_nid,
                            target_nid,
                            type=EDGE_TYPE_INVOKES
                        )
    # ──────────────────────────────────────────────────────────────────────
    return G

import asyncio
from openai import AsyncOpenAI



sem = asyncio.Semaphore(8)

async def annotate_graph_async(G: nx.MultiDiGraph, openai_client=None) -> nx.MultiDiGraph:
    if openai_client is None:
        openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=600.0)
    readme_node = next((n for n, d in G.nodes(data=True) if "readme" in n.lower()), None)
    readme_text = G.nodes[readme_node].get("code", "") if readme_node else ""

    total = 0
    completed = 0
    lock = asyncio.Lock()

    valid_nodes = [
        (nid, data)
        for nid, data in G.nodes(data=True)
        if isinstance(data, dict) and "type" in data
    ]
    total = len(valid_nodes)

    async def annotate_node_safe(nid: str, data: dict):
        nonlocal completed

        try:
            ntype = data["type"]
            context = {"readme": readme_text}

            if ntype in {"function", "class"}:
                context["code"] = data.get("code", "")
                context["file_path"] = data.get("file_path", "")
                context["node_id"] = nid
                siblings = list(G.successors(data["file_path"])) if "file_path" in data else []
                context["sibling_nodes"] = [
                    {"id": sid, "type": G.nodes[sid]["type"], "code": G.nodes[sid].get("code", "")}
                    for sid in siblings if sid != nid and G.nodes[sid].get("type") in {"function", "class"}
                ]

            elif ntype == "file":
                context["file_path"] = nid
                children = list(G.successors(nid))
                context["children"] = [
                    {"id": c, "type": G.nodes[c]["type"], "code": G.nodes[c].get("code", "")}
                    for c in children if G.nodes[c].get("type") in {"function", "class"}
                ]

            elif ntype == "generic_file":
                context["file_path"] = nid
                context["type"] = "generic file"

            elif ntype == "directory":
                children = list(G.successors(nid))
                context["children"] = [
                    {
                        "id": c,
                        "type": G.nodes[c]["type"],
                        "sample_code": next(
                            (G.nodes[g]["code"]
                             for g in G.successors(c)
                             if G.nodes[g].get("type") in {"function", "class"} and "code" in G.nodes[g]),
                            None,
                        )
                    }
                    for c in children if G.nodes[c].get("type") in {"file", "generic_file"}
                ]
            else:
                return

            async with sem:
                summary = await generate_node_summary(ntype, nid, context, openai_client)
                G.nodes[nid]["summary"] = summary

        except Exception as e:
            G.nodes[nid]["summary"] = "Summary generation failed."
            print(f"[❌] Failed to annotate {nid}: {e}")

        # Update counter
        async with lock:
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(f"[{completed}/{total}] nodes annotated")

    # Kick off tasks
    tasks = [annotate_node_safe(nid, data) for nid, data in valid_nodes[:10]]
    await asyncio.gather(*tasks)

    # Annotate edges
    for u, v, d in G.edges(data=True):
        d["summary"] = f"Node {u} {d.get('type', 'UNKNOWN')} node {v}"

    return G





import openai
from openai import OpenAI
async def generate_node_summary(ntype: str, nid: str, context: dict, openai_client: OpenAI) -> str:
    """
    Uses GPT to generate a summary for the node based on type and context.
    Requires: `client` is an instance of openai.OpenAI(api_key=...)
    """
    base = f"You are analyzing a {ntype.upper()} node from a software codebase."

    if ntype in {"function", "class"}:
        siblings = context.get("sibling_nodes", [])
        sibling_desc = "\n".join([
            f"- {s['id']}: {'(code shown)' if s.get('code') else '(code hidden)'}"
            for s in siblings[:5]
        ])
        code = context.get("code", "")
        readme = context.get("readme", "")

        prompt = f"""{base}

README:
{readme[:1500]}

Location: {context.get('file_path', '')}
Node ID: {nid}

Main Code:
{code}

Other functions/classes in this file:
{sibling_desc}

Summarize the purpose of the {ntype} in one sentence.
"""

    elif ntype == "file":
        readme = context.get("readme", "")
        children = context.get("children", [])
        code_summaries = "\n".join([
            f"- {c['id']}:\n{c['code'][:300]}\n" if c.get("code") else f"- {c['id']}: (code not available)"
            for c in children[:3]
        ])
        others = ", ".join([c["id"] for c in children[3:6]])

        prompt = f"""{base}

README:
{readme[:1500]}

File Path: {context.get('file_path', '')}

Top elements defined in file:
{code_summaries}

Other symbols: {others}

Summarize the purpose of this file in 2 sentences.
"""

    elif ntype == "generic_file":
        prompt = f"""{base}

File Path: {context.get('file_path', '')}
README:
{context.get('readme', '')[:1000]}

Give a 1-2 sentence summary of what this file might contain or why it might be useful.
"""

    elif ntype == "directory":
        children = context.get("children", [])
        child_desc = "\n".join([
            f"- {c['id']}: (sample code included)" if c.get("sample_code") else f"- {c['id']}"
            for c in children[:5]
        ])
        prompt = f"""{base}

Directory Path: {nid}
README:
{context.get('readme', '')[:1500]}

It contains the following files:
{child_desc}

Summarize the directory's purpose in 1-2 sentences.
"""
    else:
        return f"No summary available for node {nid}"



    # Correct OpenAI call using new SDK
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You're a code documentation expert."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()
