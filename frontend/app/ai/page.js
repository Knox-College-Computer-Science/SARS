"use client";
import { useState, useRef, useEffect, useCallback } from "react";

const API = "http://localhost:8000";
const DEFAULT_COURSE = "course_1";

const TABS = { CHAT: "chat", UPLOAD: "upload", FILES: "files" };

// Replace with courses fetched from Google Classroom API later
const COURSES = [
  { id: "course_1", name: "Bio 101" },
  { id: "course_2", name: "Chemistry 201" },
  { id: "course_3", name: "Physics 301" },
];

const STATUS_COLORS = {
  indexed:    "#57f287",  // green
  processing: "#fee75c",  // yellow
  error:      "#f04747",  // red
  duplicate:  "#949ba4",  // grey
};

export default function AIPage() {
  const [activeTab, setActiveTab]       = useState(TABS.CHAT);
  const [courseId, setCourseId]         = useState(DEFAULT_COURSE);
  const [messages, setMessages]         = useState([]);
  const [input, setInput]               = useState("");
  const [loading, setLoading]           = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadFile, setUploadFile]     = useState(null);
  const [useOCR, setUseOCR]            = useState(false);
  const [indexedFiles, setIndexedFiles] = useState([]);
  const [error, setError]               = useState("");
  const [streamingText, setStreamingText] = useState("");
  const bottomRef = useRef(null);

  const storageKey = `sars_chat_history_${courseId}`;

  // ── Load chat history + files when course changes ─────────────
  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try { setMessages(JSON.parse(saved)); }
      catch { setMessages([defaultWelcome()]); }
    } else {
      setMessages([defaultWelcome()]);
    }
    fetchIndexedFiles();
  }, [courseId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  useEffect(() => {
    if (messages.length > 0)
      localStorage.setItem(storageKey, JSON.stringify(messages));
  }, [messages, courseId]);

  function defaultWelcome() {
    return {
      role: "assistant",
      content: "Welcome to SARS AI. Upload course materials to get started, then ask questions about them.",
    };
  }

  const fetchIndexedFiles = async () => {
    try {
      const res = await fetch(`${API}/rag/files/${courseId}`);
      if (res.ok) {
        const data = await res.json();
        setIndexedFiles(data.files || []);
      }
    } catch (e) {
      console.error("Failed to fetch files:", e);
    }
  };

  // Poll for processing files until all are done
  useEffect(() => {
    const hasProcessing = indexedFiles.some(f => f.status === "processing");
    if (!hasProcessing) return;
    const timer = setInterval(fetchIndexedFiles, 3000);
    return () => clearInterval(timer);
  }, [indexedFiles, courseId]);

  const deduplicateCitations = (citations) => {
    if (!citations?.length) return [];
    const seen = new Set();
    return citations.filter(c => {
      const key = `${c.source}|${c.section}|${c.page}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const handleStreamingChat = async (question) => {
    setMessages(prev => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    setStreamingText("");
    setError("");

    try {
      const url = new URL(`${API}/rag/chat/stream`);
      url.searchParams.append("query", question);
      url.searchParams.append("course_id", courseId);

      const response = await fetch(url.toString());
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let citations = [];
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "citations")
              citations = deduplicateCitations(event.citations || []);
            else if (event.type === "token") {
              fullText += event.text || "";
              setStreamingText(fullText);
            } else if (event.type === "error")
              throw new Error(event.text || "Unknown error");
          } catch (e) {
            if (e.message !== "Unknown error") console.error("SSE parse error:", e);
            else throw e;
          }
        }
      }

      setMessages(prev => [...prev, { role: "assistant", content: fullText, citations }]);
      setStreamingText("");
    } catch (e) {
      setError(e.message);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Error: ${e.message}. Make sure Ollama is running.`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = () => {
    const q = input.trim();
    if (!q || loading) return;
    handleStreamingChat(q);
  };

  const handleRagUpload = async () => {
    if (!uploadFile) return;
    setUploadLoading(true);
    setError("");

    const form = new FormData();
    form.append("file", uploadFile);

    try {
      const url = new URL(`${API}/rag/upload`);
      url.searchParams.append("course_id", courseId);
      url.searchParams.append("use_ocr", useOCR ? "true" : "false");

      const res = await fetch(url.toString(), { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      const data = await res.json();
      const status = data.file?.index_result?.status;

      let msg = "";
      if (status === "duplicate")
        msg = `ℹ️ ${data.file?.file_name} is already indexed — no changes made.`;
      else if (status === "success")
        msg = `✓ Indexed ${data.file?.file_name} (${data.file?.index_result?.retrieval_chunks} chunks)`;
      else if (status === "error")
        msg = `✗ Failed to index ${data.file?.file_name}: ${data.file?.index_result?.error}`;
      else
        msg = `Processing ${data.file?.file_name}…`;

      setMessages(prev => [...prev, { role: "system", content: msg }]);
      setUploadFile(null);
      fetchIndexedFiles();
      setActiveTab(TABS.FILES);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploadLoading(false);
    }
  };

  const handleDeleteFile = async (filename, fileId) => {
    if (!window.confirm(`Delete "${filename}" and all its indexed chunks?`)) return;
    try {
      const res = await fetch(`${API}/rag/files/${courseId}/${fileId}`, { method: "DELETE" });
      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, {
          role: "system",
          content: `✓ Deleted ${filename} (${data.deleted_chunks} chunks removed)`,
        }]);
        fetchIndexedFiles();
        setActiveTab(TABS.CHAT);
      }
    } catch (e) {
      setError(`Failed to delete: ${e.message}`);
    }
  };

  const courseName = COURSES.find(c => c.id === courseId)?.name || courseId;

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-[#1e1f26] via-[#242933] to-[#1e1f26]">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
        * { font-family: 'Inter', sans-serif; }
        .tab-active { color:#f8f9fa; border-bottom:2px solid #5865f2; }
        .tab-inactive { color:#949ba4; transition:all .3s; }
        .tab-inactive:hover { color:#dbdee1; }
        .msg-enter { animation:slideIn .3s ease-out; }
        @keyframes slideIn { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        .pulse { animation:pulseSoft 2s ease-in-out infinite; }
        @keyframes pulseSoft { 0%,100%{opacity:1} 50%{opacity:.5} }
        .btn-primary { background:#5865f2; }
        .btn-primary:hover { background:#4752c4; }
        .toggle-switch { position:relative; display:inline-block; width:44px; height:22px; }
        .toggle-switch input { opacity:0; width:0; height:0; }
        .slider { position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background:#40444b; border-radius:22px; transition:.3s; }
        .slider:before { position:absolute; content:""; height:16px; width:16px; left:3px; bottom:3px; background:white; border-radius:50%; transition:.3s; }
        input:checked + .slider { background:#5865f2; }
        input:checked + .slider:before { transform:translateX(22px); }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="border-b border-[#2c2f33] bg-[#2c2f33]/30 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#5865f2] flex items-center justify-center">
                <span className="text-lg">✨</span>
              </div>
              <div>
                <h1 className="text-xl font-semibold text-[#f2f3f5]">SARS AI</h1>
                <p className="text-xs text-[#949ba4]">Course Assistant</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <select
                value={courseId}
                onChange={e => setCourseId(e.target.value)}
                className="bg-[#40444b] border border-[#36393f] rounded px-3 py-2 text-sm text-[#dbdee1] focus:outline-none focus:border-[#5865f2] transition"
              >
                {COURSES.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <div className="text-right">
                <p className="text-sm text-[#dbdee1]">{courseName}</p>
                <p className="text-xs text-[#72767d]">
                  {indexedFiles.length} file{indexedFiles.length !== 1 ? "s" : ""} indexed
                </p>
              </div>
            </div>
          </div>
          <div className="flex gap-8 border-t border-[#2c2f33] pt-4">
            {Object.values(TABS).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`pb-3 text-sm font-medium transition-all capitalize relative ${activeTab === tab ? "tab-active" : "tab-inactive"}`}>
                {tab}
                {tab === TABS.FILES && indexedFiles.some(f => f.status === "processing") && (
                  <span className="ml-2 inline-block w-2 h-2 rounded-full bg-[#fee75c] pulse" />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Main Content ────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">

        {/* CHAT TAB */}
        {activeTab === TABS.CHAT && (
          <div className="h-full flex flex-col">
            <div className="flex-1 overflow-y-auto px-6 py-6">
              <div className="max-w-4xl mx-auto space-y-4">
                {messages.map((msg, i) => (
                  <div key={i} className="msg-enter">
                    {msg.role === "system" ? (
                      <div className="inline-block bg-[#2c2f33] rounded-lg px-4 py-2 text-sm text-[#b5bac1] border border-[#40444b]">
                        {msg.content}
                      </div>
                    ) : (
                      <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`rounded-2xl px-5 py-3 max-w-2xl text-sm leading-relaxed ${
                          msg.role === "user"
                            ? "bg-[#5865f2] text-white rounded-br-none"
                            : "bg-[#36393f] text-[#dbdee1] rounded-bl-none"
                        }`}>
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                          {msg.citations?.length > 0 && (
                            <div className="mt-4 pt-3 border-t border-[#2c2f33] space-y-2">
                              {msg.citations.map((c, idx) => (
                                <div key={idx} className="text-xs opacity-80 flex gap-2">
                                  <span className="font-semibold min-w-fit text-[#5865f2]">[{idx + 1}]</span>
                                  <span>
                                    {c.source} — {c.section}, p.{c.page}
                                    <span className="opacity-60 ml-1">({c.element_type})</span>
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {loading && streamingText && (
                  <div className="flex justify-start msg-enter">
                    <div className="bg-[#36393f] text-[#dbdee1] rounded-2xl rounded-bl-none px-5 py-3 max-w-2xl text-sm leading-relaxed">
                      <p className="whitespace-pre-wrap">{streamingText}</p>
                      <span className="inline-block ml-1 pulse">▌</span>
                    </div>
                  </div>
                )}

                {loading && !streamingText && (
                  <div className="flex justify-start">
                    <div className="bg-[#36393f] rounded-2xl px-5 py-3">
                      <div className="flex gap-2">
                        {[0, 0.2, 0.4].map((d, i) => (
                          <div key={i} className="w-2 h-2 bg-[#72767d] rounded-full pulse"
                            style={{ animationDelay: `${d}s` }} />
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                <div ref={bottomRef} />
              </div>
            </div>

            <div className="border-t border-[#2c2f33] bg-[#2c2f33]/30 backdrop-blur-sm px-6 py-4">
              {error && (
                <div className="mb-3 bg-[#f04747]/15 border border-[#f04747]/30 rounded-lg px-4 py-2 text-sm text-[#f04747]">
                  {error}
                </div>
              )}
              {indexedFiles.length === 0 && (
                <div className="mb-3 bg-[#fee75c]/10 border border-[#fee75c]/30 rounded-lg px-4 py-2 text-sm text-[#fee75c]">
                  No files indexed yet.{" "}
                  <button onClick={() => setActiveTab(TABS.UPLOAD)} className="underline">
                    Upload a PDF
                  </button>{" "}
                  to start chatting.
                </div>
              )}
              <div className="max-w-4xl mx-auto flex gap-3">
                <input
                  type="text" value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSend()}
                  placeholder="Ask about your course materials…"
                  className="flex-1 bg-[#40444b] border border-[#36393f] rounded-full px-6 py-3 text-sm text-[#dbdee1] placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]/50 transition"
                  disabled={loading}
                />
                <button onClick={handleSend} disabled={!input.trim() || loading}
                  className="btn-primary disabled:opacity-40 px-6 py-3 rounded-full text-sm font-medium text-white transition-all hover:scale-105 active:scale-95">
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {/* UPLOAD TAB */}
        {activeTab === TABS.UPLOAD && (
          <div className="h-full flex flex-col items-center justify-center px-6">
            <div className="max-w-md w-full">
              <div className="text-center mb-8">
                <div className="w-16 h-16 rounded-full bg-[#5865f2] mx-auto mb-4 flex items-center justify-center">
                  <span className="text-2xl">📄</span>
                </div>
                <h2 className="text-2xl font-semibold text-[#f2f3f5] mb-2">Upload Material</h2>
                <p className="text-[#949ba4]">Add PDFs to {courseName}</p>
              </div>

              <div className="space-y-4">
                <label className="block border-2 border-dashed border-[#40444b] rounded-2xl p-8 cursor-pointer hover:border-[#5865f2] hover:bg-[#5865f2]/5 transition group">
                  <div className="text-center">
                    <div className="text-4xl mb-2 group-hover:scale-110 transition">📁</div>
                    <p className="text-[#f2f3f5] font-medium mb-1">
                      {uploadFile ? uploadFile.name : "Choose a PDF file"}
                    </p>
                    <p className="text-sm text-[#949ba4]">or drag and drop</p>
                  </div>
                  <input type="file" accept=".pdf" className="hidden"
                    onChange={e => setUploadFile(e.target.files[0])} />
                </label>

                {/* OCR Toggle */}
                <div className="flex items-center justify-between bg-[#2c2f33] rounded-lg px-4 py-3 border border-[#40444b]">
                  <div>
                    <p className="text-sm text-[#dbdee1] font-medium">Enable OCR</p>
                    <p className="text-xs text-[#72767d]">For scanned or handwritten PDFs (slower)</p>
                  </div>
                  <label className="toggle-switch">
                    <input type="checkbox" checked={useOCR} onChange={e => setUseOCR(e.target.checked)} />
                    <span className="slider" />
                  </label>
                </div>

                <button onClick={handleRagUpload} disabled={!uploadFile || uploadLoading}
                  className="w-full btn-primary disabled:opacity-40 py-3 rounded-full text-sm font-medium text-white transition-all hover:scale-105 active:scale-95">
                  {uploadLoading ? "Indexing… (images may take longer)" : "Index PDF"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* FILES TAB */}
        {activeTab === TABS.FILES && (
          <div className="h-full overflow-y-auto px-6 py-6">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-semibold text-[#f2f3f5]">Course Materials</h2>
                  <p className="text-sm text-[#949ba4]">{courseName}</p>
                </div>
                <button onClick={() => setActiveTab(TABS.UPLOAD)}
                  className="btn-primary px-4 py-2 rounded-lg text-sm font-medium text-white transition">
                  + Upload PDF
                </button>
              </div>

              {indexedFiles.length === 0 ? (
                <div className="text-center py-16">
                  <div className="text-5xl mb-4">📚</div>
                  <p className="text-[#949ba4] text-lg">No files indexed yet</p>
                  <p className="text-sm text-[#72767d] mt-2">
                    Upload PDFs to start using the AI assistant
                  </p>
                  <button onClick={() => setActiveTab(TABS.UPLOAD)}
                    className="mt-6 btn-primary px-6 py-3 rounded-full text-sm font-medium text-white transition">
                    Upload your first PDF
                  </button>
                </div>
              ) : (
                <div className="grid gap-3">
                  {indexedFiles.map((f, idx) => (
                    <div key={f.filename || idx}
                      className="bg-[#2c2f33] border border-[#40444b] rounded-lg p-4 flex items-center justify-between hover:bg-[#36393f] hover:border-[#5865f2]/50 transition msg-enter"
                      style={{ animationDelay: `${idx * 50}ms` }}>
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <span className="text-xl">
                          {f.status === "processing" ? "⏳" :
                           f.status === "error"      ? "❌" : "📄"}
                        </span>
                        <div className="min-w-0">
                          <p className="text-[#f2f3f5] font-medium truncate">{f.filename}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs font-medium"
                              style={{ color: STATUS_COLORS[f.status] || "#949ba4" }}>
                              {f.status === "processing" ? "Indexing…" :
                               f.status === "error"      ? "Failed" :
                               f.status === "duplicate"  ? "Already indexed" : "Ready"}
                            </span>
                          </div>
                        </div>
                      </div>
                      {f.status !== "processing" && (
                        <button
                          onClick={() => handleDeleteFile(f.filename, f.file_id)}
                          className="ml-4 px-4 py-2 rounded-lg text-[#f04747] hover:bg-[#f04747]/15 transition text-sm font-medium">
                          Delete
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

      </div>
    </div>
  );
}