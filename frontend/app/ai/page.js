"use client";
import { useState, useRef, useEffect } from "react";

const API = "http://localhost:8000";

export default function AIPage() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi! I'm the SARS AI assistant. Upload a PDF in the Upload tab and I can answer questions about it. What would you like to know?",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [indexedFiles, setIndexedFiles] = useState([]);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;

    const userMsg = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API}/rag/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.chunks?.map((c) => c.source).filter(Boolean),
        },
      ]);
    } catch (e) {
      setError(e.message);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry, I ran into an error: ${e.message}. Make sure Ollama is running and models are pulled.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleRagUpload = async () => {
    if (!uploadFile) return;
    setUploadLoading(true);
    setError("");
    const form = new FormData();
    form.append("file", uploadFile);
    try {
      const res = await fetch(`${API}/rag/upload`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Indexed **${data.file?.file_name}** into the knowledge base. You can now ask questions about it!`,
        },
      ]);
      setIndexedFiles((prev) => [...new Set([...prev, data.file?.file_name])]);
      setUploadFile(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploadLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#343541] text-white">
      {/* Header */}
      <div className="bg-[#202123] px-6 py-4 border-b border-gray-700 flex items-center gap-3">
        <span className="text-2xl">🤖</span>
        <div>
          <h1 className="font-semibold text-lg">AI Assistant</h1>
          <p className="text-gray-400 text-xs">
            Ask questions about your uploaded course materials
          </p>
        </div>
      </div>

      {/* Quick upload strip */}
      <div className="bg-[#2a2b32] px-6 py-3 border-b border-gray-700 flex items-center gap-3">
        <label className="text-sm text-gray-400">Index a PDF:</label>
        <input
          type="file"
          accept=".pdf"
          className="text-sm text-gray-300 flex-1"
          onChange={(e) => setUploadFile(e.target.files[0])}
        />
        <button
          onClick={handleRagUpload}
          disabled={!uploadFile || uploadLoading}
          className="bg-purple-600 hover:bg-purple-700 disabled:opacity-40 px-4 py-1.5 rounded text-sm font-medium transition"
        >
          {uploadLoading ? "Indexing…" : "Index"}
        </button>
        {indexedFiles.length > 0 && (
          <span className="text-xs text-green-400">
            {indexedFiles.length} file(s) indexed
          </span>
        )}
      </div>

      {error && (
        <div className="bg-red-900/40 text-red-300 text-sm px-6 py-2 border-b border-red-800">
          {error}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-[#444654] text-gray-100"
              }`}
            >
              {msg.content}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-600 text-xs text-gray-400">
                  Sources: {[...new Set(msg.sources)].join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-[#444654] rounded-2xl px-4 py-3 text-sm text-gray-400 animate-pulse">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="bg-[#40414f] border-t border-gray-600 px-4 py-3 flex gap-3 items-center">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask a question about your course materials…"
          className="flex-1 bg-transparent outline-none text-sm placeholder-gray-500"
          disabled={loading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          className="bg-green-500 hover:bg-green-600 disabled:opacity-40 px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          Send
        </button>
      </div>
    </div>
  );
}
