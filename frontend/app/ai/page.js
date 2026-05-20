"use client";
import { useState, useRef, useEffect } from "react";

const API = "http://localhost:8000";
const DEFAULT_COURSE = "course_1";

const TABS = {
  CHAT: "chat",
  UPLOAD: "upload",
  FILES: "files",
};

const COURSES = [
  { id: "course_1", name: "Bio 101" },
  { id: "course_2", name: "Chemistry 201" },
  { id: "course_3", name: "Physics 301" },
];

export default function AIPage() {
  const [activeTab, setActiveTab] = useState(TABS.CHAT);
  const [courseId, setCourseId] = useState(DEFAULT_COURSE);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Welcome to SARS AI. Upload course materials to get started, then ask questions about them.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [indexedFiles, setIndexedFiles] = useState([]);
  const [error, setError] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const bottomRef = useRef(null);

  const storageKey = `sars_chat_history_${courseId}`;
  const filesKey = `sars_files_${courseId}`;

  useEffect(() => {
    loadChatHistory();
    fetchIndexedFiles();
  }, [courseId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  useEffect(() => {
    saveChatHistory();
  }, [messages, courseId]);

  const loadChatHistory = () => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        setMessages(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to load chat history:", e);
      }
    } else {
      setMessages([
        {
          role: "assistant",
          content:
            "Welcome to SARS AI. Upload course materials to get started, then ask questions about them.",
        },
      ]);
    }
  };

  const saveChatHistory = () => {
    localStorage.setItem(storageKey, JSON.stringify(messages));
  };

  const fetchIndexedFiles = async () => {
    try {
      const res = await fetch(`${API}/rag/files/${courseId}`);
      if (res.ok) {
        const data = await res.json();
        setIndexedFiles(data.files || []);
        localStorage.setItem(filesKey, JSON.stringify(data.files || []));
      }
    } catch (e) {
      console.error("Failed to fetch files:", e);
      const cached = localStorage.getItem(filesKey);
      if (cached) {
        setIndexedFiles(JSON.parse(cached));
      }
    }
  };

  const deduplicateCitations = (citations) => {
    if (!citations || citations.length === 0) return [];

    const seen = new Set();
    return citations.filter((c) => {
      const key = `${c.source}|${c.section}|${c.page}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  };

  const handleStreamingChat = async (question) => {
    const userMsg = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setStreamingText("");
    setError("");

    try {
      const url = new URL(`${API}/rag/chat/stream`);
      url.searchParams.append("query", question);
      url.searchParams.append("course_id", courseId);

      const response = await fetch(url.toString());

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let citations = [];
      let fullText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));

              if (event.type === "citations") {
                citations = deduplicateCitations(event.citations || []);
              } else if (event.type === "token") {
                fullText += event.text || "";
                setStreamingText(fullText);
              } else if (event.type === "done") {
                continue;
              } else if (event.type === "error") {
                throw new Error(event.text || "Unknown error");
              }
            } catch (e) {
              console.error("Failed to parse SSE event:", e);
            }
          }
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: fullText,
          citations: citations,
        },
      ]);
      setStreamingText("");
    } catch (e) {
      setError(e.message);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${e.message}. Make sure Ollama is running.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;
    await handleStreamingChat(q);
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

      const res = await fetch(url.toString(), { method: "POST", body: form });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: `✓ Indexed ${data.file?.file_name} (${data.file?.index_result?.retrieval_chunks} chunks)`,
        },
      ]);
      setUploadFile(null);
      fetchIndexedFiles();
      setActiveTab(TABS.CHAT);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploadLoading(false);
    }
  };

  const handleDeleteFile = async (fileName, fileId) => {
    if (!window.confirm(`Delete ${fileName}?`)) return;

    try {
      const res = await fetch(
        `${API}/rag/files/${courseId}/${fileId}`,
        { method: "DELETE" }
      );

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: "system",
            content: `✓ Deleted ${fileName} (${data.deleted_chunks} chunks removed)`,
          },
        ]);
        fetchIndexedFiles();
      }
    } catch (e) {
      setError(`Failed to delete file: ${e.message}`);
    }
  };

  const courseName = COURSES.find((c) => c.id === courseId)?.name || courseId;

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-[#1e1f26] via-[#242933] to-[#1e1f26]">
      <style>{`
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
        * {
          font-family: 'Inter', sans-serif;
        }
        .tab-active {
          color: #f8f9fa;
          border-bottom: 2px solid #5865f2;
        }
        .tab-inactive {
          color: #949ba4;
          transition: all 0.3s ease;
        }
        .tab-inactive:hover {
          color: #dbdee1;
        }
        .message-enter {
          animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .pulse-subtle {
          animation: pulseSoft 2s ease-in-out infinite;
        }
        @keyframes pulseSoft {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .discord-button {
          background: #5865f2;
        }
        .discord-button:hover {
          background: #4752c4;
        }
      `}</style>
      {/* Header */}
      <div className="border-b border-[#2c2f33] bg-[#2c2f33]/30 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#5865f2] flex items-center justify-center">
                <span className="text-lg">✨</span>
              </div>
              <div>
                <h1 className="text-xl font-semibold text-[#f2f3f5]">SARS</h1>
                <p className="text-xs text-[#949ba4]">AI Course Assistant</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <select
                value={courseId}
                onChange={(e) => setCourseId(e.target.value)}
                className="bg-[#40444b] border border-[#36393f] rounded px-3 py-2 text-sm text-[#dbdee1] hover:bg-[#494d52] focus:outline-none focus:border-[#5865f2] transition"
              >
                {COURSES.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.name}
                  </option>
                ))}
              </select>
              <div className="text-right">
                <p className="text-sm text-[#dbdee1]">{courseName}</p>
                <p className="text-xs text-[#72767d]">Streaming enabled</p>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-8 border-t border-[#2c2f33] pt-4">
            {Object.values(TABS).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`pb-3 text-sm font-medium transition-all duration-300 capitalize ${
                  activeTab === tab ? "tab-active" : "tab-inactive"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === TABS.CHAT && (
          <div className="h-full flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-6">
              <div className="max-w-4xl mx-auto space-y-4">
                {messages.map((msg, i) => (
                  <div key={i} className="message-enter">
                    {msg.role === "system" ? (
                      <div className="inline-block bg-[#2c2f33] rounded-lg px-4 py-2 text-sm text-[#b5bac1] border border-[#40444b]">
                        {msg.content}
                      </div>
                    ) : (
                      <div
                        className={`flex ${
                          msg.role === "user" ? "justify-end" : "justify-start"
                        }`}
                      >
                        <div
                          className={`rounded-2xl px-5 py-3 max-w-2xl text-sm leading-relaxed ${
                            msg.role === "user"
                              ? "bg-[#5865f2] text-white rounded-br-none"
                              : "bg-[#36393f] text-[#dbdee1] rounded-bl-none"
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{msg.content}</p>

                          {msg.citations && msg.citations.length > 0 && (
                            <div className="mt-4 pt-3 border-t border-[#2c2f33] space-y-2">
                              {msg.citations.map((c, idx) => (
                                <div
                                  key={idx}
                                  className="text-xs opacity-80 flex gap-2"
                                >
                                  <span className="font-semibold min-w-fit text-[#5865f2]">
                                    [{idx + 1}]
                                  </span>
                                  <span>
                                    {c.source} — {c.section}, p.{c.page}{" "}
                                    <span className="opacity-60">
                                      ({c.element_type})
                                    </span>
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
                  <div className="flex justify-start message-enter">
                    <div className="bg-[#36393f] text-[#dbdee1] rounded-2xl rounded-bl-none px-5 py-3 max-w-2xl text-sm leading-relaxed">
                      <p className="whitespace-pre-wrap">{streamingText}</p>
                      <span className="inline-block ml-1 pulse-subtle">▌</span>
                    </div>
                  </div>
                )}

                {loading && !streamingText && (
                  <div className="flex justify-start">
                    <div className="bg-[#36393f] rounded-2xl px-5 py-3">
                      <div className="flex gap-2">
                        <div className="w-2 h-2 bg-[#72767d] rounded-full pulse-subtle" />
                        <div
                          className="w-2 h-2 bg-[#72767d] rounded-full pulse-subtle"
                          style={{ animationDelay: "0.2s" }}
                        />
                        <div
                          className="w-2 h-2 bg-[#72767d] rounded-full pulse-subtle"
                          style={{ animationDelay: "0.4s" }}
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div ref={bottomRef} />
              </div>
            </div>

            {/* Input */}
            <div className="border-t border-[#2c2f33] bg-[#2c2f33]/30 backdrop-blur-sm px-6 py-4">
              {error && (
                <div className="mb-3 bg-[#f04747]/15 border border-[#f04747]/30 rounded-lg px-4 py-2 text-sm text-[#f04747]">
                  {error}
                </div>
              )}
              <div className="max-w-4xl mx-auto flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && !e.shiftKey && handleSend()
                  }
                  placeholder="Ask about your course materials..."
                  className="flex-1 bg-[#40444b] border border-[#36393f] rounded-full px-6 py-3 text-sm text-[#dbdee1] placeholder-[#72767d] focus:outline-none focus:ring-2 focus:ring-[#5865f2]/50 focus:border-transparent transition"
                  disabled={loading}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || loading}
                  className="discord-button disabled:opacity-40 disabled:cursor-not-allowed px-6 py-3 rounded-full text-sm font-medium text-white transition-all duration-200 transform hover:scale-105 active:scale-95"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === TABS.UPLOAD && (
          <div className="h-full flex flex-col items-center justify-center px-6">
            <div className="max-w-md w-full">
              <div className="text-center mb-8">
                <div className="w-16 h-16 rounded-full bg-[#5865f2] mx-auto mb-4 flex items-center justify-center">
                  <span className="text-2xl">📄</span>
                </div>
                <h2 className="text-2xl font-semibold text-[#f2f3f5] mb-2">
                  Upload Material
                </h2>
                <p className="text-[#949ba4]">
                  Add PDFs to {courseName}
                </p>
              </div>

              <div className="space-y-4">
                <label className="block border-2 border-dashed border-[#40444b] rounded-2xl p-8 cursor-pointer hover:border-[#5865f2] hover:bg-[#5865f2]/5 transition group">
                  <div className="text-center">
                    <div className="text-4xl mb-2 group-hover:scale-110 transition">
                      📁
                    </div>
                    <p className="text-[#f2f3f5] font-medium mb-1">
                      Choose a PDF file
                    </p>
                    <p className="text-sm text-[#949ba4]">
                      or drag and drop
                    </p>
                  </div>
                  <input
                    type="file"
                    accept=".pdf"
                    className="hidden"
                    onChange={(e) => setUploadFile(e.target.files[0])}
                  />
                </label>

                {uploadFile && (
                  <div className="bg-[#2c2f33] rounded-lg p-4 border border-[#40444b]">
                    <p className="text-sm text-[#dbdee1]">
                      📌 {uploadFile.name}
                    </p>
                  </div>
                )}

                <button
                  onClick={handleRagUpload}
                  disabled={!uploadFile || uploadLoading}
                  className="w-full discord-button disabled:opacity-40 py-3 rounded-full text-sm font-medium text-white transition-all duration-200 transform hover:scale-105 active:scale-95"
                >
                  {uploadLoading ? "Indexing..." : "Index PDF"}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === TABS.FILES && (
          <div className="h-full overflow-y-auto px-6 py-6">
            <div className="max-w-4xl mx-auto">
              <h2 className="text-2xl font-semibold text-[#f2f3f5] mb-2">
                Course Materials
              </h2>
              <p className="text-sm text-[#949ba4] mb-6">
                {courseName}
              </p>

              {indexedFiles.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-4xl mb-3">📚</div>
                  <p className="text-[#949ba4]">No files indexed yet</p>
                  <p className="text-sm text-[#72767d] mt-2">
                    Upload PDFs in the Upload tab to get started
                  </p>
                </div>
              ) : (
                <div className="grid gap-3">
                  {indexedFiles.map((f, idx) => (
                    <div
                      key={f.filename}
                      className="bg-[#2c2f33] border border-[#40444b] rounded-lg p-4 flex items-center justify-between hover:bg-[#36393f] hover:border-[#5865f2]/50 transition group message-enter"
                      style={{ animationDelay: `${idx * 50}ms` }}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <span className="text-xl">📄</span>
                        <div className="min-w-0">
                          <p className="text-[#f2f3f5] font-medium truncate">
                            {f.filename}
                          </p>
                          <p className="text-xs text-[#949ba4]">
                            {f.context_count || 0} chunks indexed
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleDeleteFile(f.filename, f.filename)}
                        className="ml-4 px-4 py-2 rounded-lg text-[#f04747] hover:bg-[#f04747]/15 hover:text-[#f04747] transition text-sm font-medium"
                      >
                        Delete
                      </button>
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