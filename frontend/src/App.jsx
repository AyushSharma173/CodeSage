import { useState, useRef, useEffect } from "react";
import { uploadRepo, askQuestion } from "./api";
import ReactMarkdown from "react-markdown";
import NodeViewer from "./NodeViewer";

function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [docUrl, setDocUrl] = useState("");
  const [isRepoSubmitted, setIsRepoSubmitted] = useState(false);
  const [repoId, setRepoId] = useState(null);

  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [strategy, setStrategy] = useState("invokes_only");

  const strategyOptions = [
    { label: "Invokes Only", value: "invokes_only" },
    { label: "Contains Only", value: "contains_only" },
    { label: "Imports Only", value: "imports_only" },
    { label: "Deep Chain (All Rels)", value: "default_bfs_all" },
  ];

  const messagesEndRef = useRef(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  const handleRepoSubmit = async () => {
    if (!repoUrl.trim()) return alert("Please enter a repo URL");
    try {
      const res = await uploadRepo(repoUrl);
      setIsRepoSubmitted(true);
      setRepoId(repoUrl);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    const newHistory = [...chatHistory, { sender: "user", text: question }];
    setChatHistory(newHistory);
    setLoading(true);
    setQuestion("");

    try {
      const res = await askQuestion(question, repoId, 5, strategy);
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

  return (
    <div
      style={{
        backgroundColor: "#F9FAFB",
        minHeight: "100vh",
        padding: "2rem",
        fontFamily: "Inter, sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: "100%",
      }}
    >
      <h1 style={{ color: "#1F2937", marginBottom: "2rem", fontSize: "2.5rem" }}>CodeBase Agent</h1>

      {!isRepoSubmitted ? (
        <div style={{ width: "100%", maxWidth: "900px", padding: "0 1rem" }}>
          <input
            type="text"
            placeholder="GitHub Repo URL"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            style={{
              width: "100%",
              padding: "1rem",
              marginBottom: "1rem",
              border: "1px solid #D1D5DB",
              borderRadius: "8px",
              backgroundColor: "#FFFFFF",
              color: "#111827",
              fontSize: "1rem",
            }}
          />

          <input
            type="text"
            placeholder="(Optional) Documentation URL"
            value={docUrl}
            onChange={(e) => setDocUrl(e.target.value)}
            style={{
              width: "100%",
              padding: "1rem",
              marginBottom: "1.5rem",
              border: "1px solid #D1D5DB",
              borderRadius: "8px",
              backgroundColor: "#FFFFFF",
              color: "#111827",
              fontSize: "1rem",
            }}
          />

          <button
            onClick={handleRepoSubmit}
            style={{
              padding: "0.75rem 2rem",
              backgroundColor: "#2563EB",
              color: "#FFFFFF",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              fontSize: "1rem",
              fontWeight: "500",
            }}
          >
            Upload Repo
          </button>
        </div>
      ) : (
        <div style={{ width: "100%", maxWidth: "1600px", padding: "0 1rem" }}>
          <h2 style={{ color: "#374151", marginBottom: "1.5rem", fontSize: "1.5rem" }}>
            Repo Indexed! Start chatting below:
          </h2>

          {/* Strategy Dropdown */}
          <div style={{ marginBottom: "1rem", textAlign: "left" }}>
            <label style={{ marginRight: "0.75rem", fontWeight: "500", color: "#1F2937", fontSize: "1rem" }}>
              Retrieval Strategy:
            </label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              style={{
                padding: "0.5rem 1rem",
                border: "1px solid #D1D5DB",
                borderRadius: "8px",
                backgroundColor: "#FFFFFF",
                color: "#111827",
                fontSize: "1rem",
              }}
            >
              {strategyOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", gap: "2rem", width: "100%" }}>
            {/* Chat Panel */}
            <div style={{ width: "50%" }}>
              <div
                style={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #E5E7EB",
                  borderRadius: "10px",
                  padding: "1rem",
                  maxHeight: "450px",
                  overflowY: "auto",
                  marginBottom: "1rem",
                }}
              >
                {chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      justifyContent: msg.sender === "user" ? "flex-end" : "flex-start",
                      marginBottom: "1rem",
                    }}
                  >
                    <div
                      style={{
                        backgroundColor: msg.sender === "user" ? "#2563EB" : "#4B5563",
                        padding: "0.75rem 1rem",
                        borderRadius: "12px",
                        maxWidth: "75%",
                        lineHeight: "1.5",
                        color: "#FFFFFF",
                        fontSize: "0.95rem",
                      }}
                    >
                      <ReactMarkdown>{msg.text}</ReactMarkdown>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <input
                  type="text"
                  placeholder="Ask something about the code..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                  style={{
                    flex: 1,
                    padding: "0.75rem 1rem",
                    border: "1px solid #CBD5E1",
                    borderRadius: "8px",
                    backgroundColor: "#FFFFFF",
                    color: "#1F2937",
                    fontSize: "1rem",
                  }}
                />
                <button
                  onClick={handleAsk}
                  disabled={loading}
                  style={{
                    padding: "0.75rem 2rem",
                    backgroundColor: "#2563EB",
                    color: "#FFFFFF",
                    border: "none",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontWeight: "500",
                    fontSize: "1rem",
                  }}
                >
                  {loading ? "Thinking..." : "Ask"}
                </button>
              </div>
            </div>

            {/* NodeViewer Panel */}
            <div
              style={{
                width: "50%",
                borderLeft: "1px solid #E5E7EB",
                paddingLeft: "1rem",
              }}
            >
              {chatHistory.length > 0 &&
                chatHistory[chatHistory.length - 1].context && (
                  <NodeViewer context={chatHistory[chatHistory.length - 1].context} />
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
