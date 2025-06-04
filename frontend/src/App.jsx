// src/App.jsx
import { useState, useRef, useEffect } from "react";
import { uploadRepo, askQuestion, getFullGraph } from "./api";
import ReactMarkdown from "react-markdown";
import NodeViewer from "./NodeViewer";
import GraphView from "./GraphView";
import RetrievalSettings from "./RetrievalSettings";
import "./App.css";
import "./index.css";

export default function App() {
  // ─────────────────────────────────────────────────
  // 1) Repo‐upload state
  // ─────────────────────────────────────────────────
  const [repoUrl, setRepoUrl] = useState("");
  const [docUrl, setDocUrl] = useState("");
  const [isRepoSubmitted, setIsRepoSubmitted] = useState(false);
  const [repoId, setRepoId] = useState(null);

  // ─────────────────────────────────────────────────
  // 2) Chat + hyperparameter state
  // ─────────────────────────────────────────────────
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  // Retrieval hyperparameters
  const [strategy, setStrategy] = useState("invokes_only");
  const [depth, setDepth] = useState(2);
  const [edgeTypes, setEdgeTypes] = useState([]);
  const [includeNodeTypes, setIncludeNodeTypes] = useState([]);
  const [directed, setDirected] = useState(true);
  const [includeIncoming, setIncludeIncoming] = useState(true);
  const [includeOutgoing, setIncludeOutgoing] = useState(true);

  // ─────────────────────────────────────────────────
  // 3) Show/Hide Context Drawer state
  // ─────────────────────────────────────────────────
  const [isContextOpen, setIsContextOpen] = useState(false);

  // ─────────────────────────────────────────────────
  // 4) Show/Hide Full-graph overlay state
  // ─────────────────────────────────────────────────
  const [showGraph, setShowGraph] = useState(false);

  // Preset dropdown/multi‐select options
  const strategyOptions = [
    { label: "Invokes Only", value: "invokes_only" },
    { label: "Shallow Contains Only", value: "shallow_contains" },
    { label: "File + Function Only", value: "file_and_function_only" },
    { label: "Deep Logic Chain", value: "deep_logic_chain" },
    { label: "Class Hierarchy", value: "class_hierarchy" },
    { label: "Default BFS (All Rel Types)", value: "default_bfs_all" },
  ];
  const allEdgeTypes = [
    { label: "contains", value: "contains" },
    { label: "invokes", value: "invokes" },
    { label: "inherits", value: "inherits" },
    { label: "imports", value: "imports" },
  ];
  const allNodeTypes = [
    { label: "directory", value: "directory" },
    { label: "file", value: "file" },
    { label: "class", value: "class" },
    { label: "function", value: "function" },
    { label: "generic_file", value: "generic_file" },
  ];

  // ─────────────────────────────────────────────────
  // 5) Refs for auto‐scrolling chat
  // ─────────────────────────────────────────────────
  const chatContainerRef = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (chatHistory.length === 0) return;
    const lastMsg = chatHistory[chatHistory.length - 1];
    // Only auto‐scroll when the latest entry is from the bot
    if (lastMsg.sender === "bot" && chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory]);

  // ─────────────────────────────────────────────────
  // 6) “Upload & Index Repo” handler
  // ─────────────────────────────────────────────────
  const handleRepoSubmit = async () => {
    if (!repoUrl.trim()) {
      alert("Please enter a GitHub repo URL.");
      return;
    }
    try {
      await uploadRepo(repoUrl);
      setIsRepoSubmitted(true);
      setRepoId(repoUrl);
    } catch (err) {
      alert(err.message || "Failed to upload repo");
    }
  };

  // ─────────────────────────────────────────────────
  // 6a) “Preset: Try Requests Repo” handler
  // ─────────────────────────────────────────────────
  const handleTryRequests = async () => {
    const presetUrl = "https://github.com/psf/requests.git";
    try {
      await uploadRepo(presetUrl);
      setIsRepoSubmitted(true);
      setRepoId(presetUrl);
    } catch (err) {
      alert(err.message || "Failed to upload Requests repo");
    }
  };

  // ─────────────────────────────────────────────────
  // 7) “Ask” button handler
  // ─────────────────────────────────────────────────
  const handleAsk = async () => {
    if (!question.trim()) return;

    // 7a) Append the user’s question to chatHistory
    const newHistory = [...chatHistory, { sender: "user", text: question }];
    setChatHistory(newHistory);
    setLoading(true);
    setQuestion("");

    try {
      const payload = {
        question,
        top_k: 5,
        repo_id: repoId,
        strategy,
        depth,
        edge_types: edgeTypes.length ? edgeTypes : null,
        include_node_types: includeNodeTypes.length ? includeNodeTypes : null,
        directed,
        include_incoming: includeIncoming,
        include_outgoing: includeOutgoing,
      };
      const res = await askQuestion(payload);

      // 7b) Append the bot’s answer (this triggers auto‐scroll)
      setChatHistory([
        ...newHistory,
        { sender: "bot", text: res.answer, context: res.context },
      ]);
    } catch (err) {
      setChatHistory([
        ...newHistory,
        { sender: "bot", text: `❌ ${err.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────
  // 8) Helper for toggling multi‐select
  // ─────────────────────────────────────────────────
  const toggleSelection = (value, currentArray, setArray) => {
    if (currentArray.includes(value)) {
      setArray(currentArray.filter((x) => x !== value));
    } else {
      setArray([...currentArray, value]);
    }
  };

  // ─────────────────────────────────────────────────
  // 8a) “Reset to Home” handler (for clicking the header)
  // ─────────────────────────────────────────────────
  const handleGoHome = () => {
    setIsRepoSubmitted(false);
    setRepoId(null);
    setChatHistory([]);
    setRepoUrl("");
    setDocUrl("");
    // Optionally reset hyperparameters if desired:
    setStrategy("invokes_only");
    setDepth(2);
    setEdgeTypes([]);
    setIncludeNodeTypes([]);
    setDirected(true);
    setIncludeIncoming(true);
    setIncludeOutgoing(true);
  };

  // ──────────────────────────────────────────────────
  // 9) RENDER
  return (
    <div className="app-root">
      {/* ── HEADER (fixed height) ── */}
      <header
        className="app-header"
        onClick={handleGoHome}
        style={{ cursor: "pointer" }}
      >
        CodeBase Agent
      </header>

      {/* ── If repo not submitted, show “Home” form ── */}
      {!isRepoSubmitted ? (
        <div className="home-container">
          <div className="home-card">
            <h2 className="home-title">Index a GitHub Repo</h2>

            {/* ── PRESET BUTTON for “Requests” ── */}
            <div className="home-field">
              <button className="home-button" onClick={handleTryRequests}>
                Try “Requests” Demo
              </button>
            </div>

            {/* ── OR custom URL ── */}
            <div className="home-field">
              <label className="home-label">GitHub Repo URL</label>
              <input
                type="text"
                placeholder="https://github.com/owner/repo.git"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                className="home-input"
              />
            </div>

            <div className="home-field">
              <label className="home-label">(Optional) Documentation URL</label>
              <input
                type="text"
                placeholder="https://some-doc-page.com"
                value={docUrl}
                onChange={(e) => setDocUrl(e.target.value)}
                className="home-input"
              />
            </div>

            <button className="home-button" onClick={handleRepoSubmit}>
              Upload & Index Repo
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* ── “View Full Graph” button bar ── */}
          <div className="graph-button-bar">
            <button
              onClick={() => setShowGraph(true)}
              className="graph-button"
            >
              View Full Graph
            </button>
          </div>

          {/* ── CHAT PAGE: left sidebar + chat panel + bottom drawer ── */}
          <div className="chat-container">
            {/* ── LEFT SIDEBAR: Retrieval Settings ── */}
            <RetrievalSettings
              strategy={strategy}
              setStrategy={setStrategy}
              depth={depth}
              setDepth={setDepth}
              edgeTypes={edgeTypes}
              setEdgeTypes={setEdgeTypes}
              includeNodeTypes={includeNodeTypes}
              setIncludeNodeTypes={setIncludeNodeTypes}
              directed={directed}
              setDirected={setDirected}
              includeIncoming={includeIncoming}
              setIncludeIncoming={setIncludeIncoming}
              includeOutgoing={includeOutgoing}
              setIncludeOutgoing={setIncludeOutgoing}
              strategyOptions={strategyOptions}
              allEdgeTypes={allEdgeTypes}
              allNodeTypes={allNodeTypes}
              toggleSelection={toggleSelection}
            />

            {/* ── CENTER: Chat Panel ── */}
            <main className="chat-main">
              {/* Chat history */}
              <div ref={chatContainerRef} className="chat-history">
                {chatHistory.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`chat-bubble ${
                      msg.sender === "user" ? "bubble-user" : "bubble-bot"
                    }`}
                  >
                    <div>
                      <ReactMarkdown>{msg.text}</ReactMarkdown>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Input + Ask + Toggle Context Drawer */}
              <div className="chat-input-bar">
                <input
                  type="text"
                  placeholder="Ask something about the code..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                  className="chat-input"
                />
                <button
                  onClick={handleAsk}
                  disabled={loading}
                  className="chat-button"
                >
                  {loading ? "Thinking..." : "Ask"}
                </button>
                <button
                  onClick={() => setIsContextOpen((prev) => !prev)}
                  className={`context-button ${
                    isContextOpen ? "btn-hide" : "btn-show"
                  }`}
                >
                  {isContextOpen ? "Hide Context" : "Show Context"}
                </button>
              </div>
            </main>

            {/* ── BOTTOM DRAWER: Retrieved Context ── */}
            <div
              className={`context-drawer ${
                isContextOpen ? "drawer-open" : "drawer-closed"
              }`}
            >
              <div
                className="drawer-header"
                onClick={() => setIsContextOpen((prev) => !prev)}
              >
                <h4 className="drawer-title">Retrieved Context</h4>
                <span className="drawer-icon">
                  {isContextOpen ? "▾" : "▴"}
                </span>
              </div>

              {isContextOpen && chatHistory.length > 0 && (
                <div className="drawer-content">
                  <NodeViewer
                    context={chatHistory[chatHistory.length - 1].context}
                  />
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Conditionally show the full-graph overlay ── */}
      {showGraph && <GraphView repoId={repoId} onClose={() => setShowGraph(false)} />}
    </div>
  );
}
