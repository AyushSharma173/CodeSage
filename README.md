# CodeGraph – Build & Query Code‑Dependency Graphs with Neo4j + LLMs

> **Prototype status** – This is a research/portfolio project, not a production‑ready service. It works on small‑to‑medium Python repos (e.g. `psf/requests`, `sdispater/pendulum`). PRs are welcome!

---

## ✨ What it does

1. **Clone any public GitHub repo** (Python‑first, multi‑language support WIP).
2. **Static‑analyze** the repo and turn it into a typed graph *(directory → file → class/function + cross‑file imports/invokes/inherits)* using **NetworkX**.
3. **Generate 1‑sentence summaries** for every node with the OpenAI API (async); store them as node properties.
4. **Push graph to Neo4j** and **embed every node** (OpenAI Embeddings → Qdrant).
5. **Answer natural‑language questions** by retrieving similar nodes (vector search) + their neighbourhood (Neo4j) and feeding that context to an LLM.
6. **Visualise & chat** in a minimal React frontend.

---

## 🔧 Architecture (bird’s‑eye)

```text
┌──────────┐       clone        ┌────────────┐               push               ┌────────────┐
│  Front‑  │ ───────────────▶  │ build_graph│  nodes/edges  ───────────────▶   │  Neo4j DB  │
│   end    │                   │  (+annotate)│──────────────┐                  └────────────┘
└──────────┘   ask/query ▶     └────────────┘               │                       ▲
      ▲  ▲                                        embeddings │                       │ Cypher
      │  │ REST                                      ▼       │                       │
      │  │                            ┌──────────────────────┴─────┐                │
      │  │                            │      Qdrant (vector)       │                │
      │  └────────────────────────────┴─────────────▲──────────────┘                │
      │                               nearest IDs   │                               │
      │                                             │                               │
      └──────────────────────────────────────────────┴───────────────────────────────┘
                           LLM (OpenAI chat) for final answer
```

---

## 🚀 Quick start (local, two terminals)

### 1 · Clone & install

```bash
# backend
git clone https://github.com/yourname/CodeGraph.git
cd CodeGraph
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2 · Create `.env` (never commit!)

```bash
# .env  – copy this template and fill in real secrets
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=sk‑...
QDRANT_API_KEY=your_qdrant_key
VECTOR_STORE_URL=http://localhost:6333  # default docker port
FRONTEND_ORIGIN=http://localhost:5173
```

### 3 · Run services

```bash
# Neo4j
# (desktop app or docker: docker run -p 7474:7474 -p 7687:7687 neo4j:5-community)

# Qdrant (vector DB)
docker run -p 6333:6333 qdrant/qdrant

# Backend (FastAPI, port 8000)
uvicorn backend.main:app --reload --port 8000
```

### 4 · Frontend

```bash
cd frontend
npm install
npm run dev    # default Vite port 5173
```

Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## 🏃🏻‍♂️ Demo repos

In the landing page click the small buttons under **“Or try a demo repo”**:

| Button               | Repo URL                                                                       | Size        |
| -------------------- | ------------------------------------------------------------------------------ | ----------- |
| `psf/requests`       | [https://github.com/psf/requests](https://github.com/psf/requests)             | \~210 files |
| `sdispater/pendulum` | [https://github.com/sdispater/pendulum](https://github.com/sdispater/pendulum) | \~80 files  |

They will auto‑index and drop you into the chat view.

---

## 🔑 Environment variables (backend)

| var                | required | example                 |
| ------------------ | -------- | ----------------------- |
| `OPENAI_API_KEY`   | ✅        | `sk‑...`                |
| `NEO4J_URI`        | ✅        | `bolt://localhost:7687` |
| `NEO4J_USER`       | ✅        | `neo4j`                 |
| `NEO4J_PASSWORD`   | ✅        | `password`              |
| `QDRANT_API_KEY`   | ✅*¹*     | `qdrant‑token`          |
| `VECTOR_STORE_URL` | ✅        | `http://localhost:6333` |
| `FRONTEND_ORIGIN`  | ✅        | `http://localhost:5173` |

> *¹* If you run Qdrant **locally** without auth you can omit `QDRANT_API_KEY`.

---

## 📂 Project structure (high‑level)

```text
CodeGraph/
├── backend/
│   ├── main.py               # FastAPI routes
│   └── app/
│       ├── graph_builder.py  # static analysis → networkx graph
│       ├── neo4j_client.py   # Graph DB helpers & queries
│       ├── vector_store.py   # Qdrant helpers
│       ├── embedder.py       # OpenAI embeddings
│       ├── repo_handler.py   # git clone + cache
│       └── query_router.py   # retrieval + LLM answer
├── frontend/
│   ├── src/App.jsx           # main React app
│   ├── src/GraphView.jsx     # full‑graph visualisation
│   ├── src/RetrievalSettings.jsx
│   └── ...
├── requirements.txt
├── .env.example              # <‑‑ commit this, not real secrets
└── README.md (this file)
```

---

## 🗄️ API endpoints (backend)

| Method | Path               | Purpose                             |
| ------ | ------------------ | ----------------------------------- |
| `POST` | `/upload-repo`     | Clone+index a repo                  |
| `POST` | `/ask`             | Ask a NL question about a repo      |
| `GET`  | `/graph/{repo_id}` | Get **all** nodes/edges for a repo  |
| `POST` | `/reset`           | Delete *all* graphs & vectors (dev) |

---

## 🧰 Development & testing

```bash
# run fast API tests
pytest tests/
# lint (add your own flake8 / black / eslint configs)
```

---

## 📝 Roadmap / Future work

* Multi‑language static analysis (JavaScript, Java, Go)
* Incremental re‑index on git commits
* Graph‑based ranking heuristics (PageRank, degree centrality)
* Full SWE‑Bench evaluation, automated benchmarks
* Docker‑compose for one‑command spin‑up

---

## 🤝 Contributing

PRs to fix bugs, add language support or improve UI are welcome. Please file an issue first to discuss large changes.

1. Fork and clone
2. `pre‑commit install` (optional) for auto‑formatting
3. Create feature branch → commit → open PR

---

## ⚖️ License

MIT – see `LICENSE`.

---

## 🙏 Acknowledgements

* Idea inspired by OpenAI’s code‑insights demo & Palantir’s code graph tooling.
* Uses **OpenAI API**, **Neo4j Community Edition**, **Qdrant**, **NetworkX**, **React**.
