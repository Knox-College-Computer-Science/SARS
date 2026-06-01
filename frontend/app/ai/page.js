"use client";
import { useState, useEffect, useRef } from "react";
import styles from "./page.module.css";
import ConnectGoogleClassroomCard from "../components/ConnectGoogleClassroomCard";

const LABEL_COLORS = [
  "var(--color-primary)",
  "var(--color-secondary-container)",
  "var(--color-tertiary)",
  "var(--color-error)",
];

const aiCache = {
  courses:     null,
  isConnected: null,
};

function getLabelColor(labelName) {
  let hash = 0;
  for (let i = 0; i < labelName.length; i++) {
    hash = labelName.charCodeAt(i) + ((hash << 5) - hash);
  }
  return LABEL_COLORS[Math.abs(hash) % LABEL_COLORS.length];
}

function CitationChip({ citation, indexedFiles, onUpdateLabels }) {
  const [open, setOpen] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const ref = useRef(null);

  const fileData = indexedFiles.find(
    f => f.filename === citation.source || f.file_id === citation.file_id
  );
  const labels   = fileData?.labels || [];
  const dotColor = getLabelColor(citation.source || "");

  useEffect(() => {
    if (!open) return;
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function handleAddLabel() {
    const trimmed = newLabel.trim();
    if (!trimmed || labels.includes(trimmed)) return;
    onUpdateLabels(fileData?.file_id, [...labels, trimmed]);
    setNewLabel("");
  }

  function handleRemoveLabel(label) {
    onUpdateLabels(fileData?.file_id, labels.filter(l => l !== label));
  }

  const displayName = citation.source?.split("/").pop()?.replace(/\.[^.]+$/, "") || citation.source;

  return (
    <div style={{ position: "relative" }} ref={ref}>
      <button className={styles.citationChip} onClick={() => setOpen(o => !o)}>
        <span className={styles.citationDot} style={{ background: dotColor }} />
        {displayName}
        {citation.page && <span style={{ opacity: 0.5 }}>p.{citation.page}</span>}
      </button>

      {open && (
        <div className={styles.labelOverlay}>
          <div className={styles.labelOverlayHeader}>
            <span className={styles.labelOverlayTitle}>Label this source</span>
            <button className={styles.labelOverlayClose} onClick={() => setOpen(false)}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
            </button>
          </div>

          {labels.length > 0 && (
            <div className={styles.existingLabels}>
              {labels.map((label, i) => (
                <span key={i} className={styles.existingLabel}
                  style={{ color: getLabelColor(label) }}>
                  {label}
                  <button className={styles.removeLabelBtn} onClick={() => handleRemoveLabel(label)}>
                    <span className="material-symbols-outlined" style={{ fontSize: 12 }}>close</span>
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className={styles.labelInput}>
            <input
              className={styles.labelInputField}
              value={newLabel}
              onChange={e => setNewLabel(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleAddLabel()}
              placeholder="Add a label…"
            />
            <button className={styles.labelAddBtn} onClick={handleAddLabel}>Add</button>
          </div>
        </div>
      )}
    </div>
  );
}

function UploadModal({ courseId, courseName, onClose, onIndexed }) {
  const [tab,          setTab         ] = useState("local");
  const [uploadFile,   setUploadFile  ] = useState(null);
  const [uploading,    setUploading   ] = useState(false);
  const [error,        setError       ] = useState("");
  const [notesFiles,   setNotesFiles  ] = useState([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [indexingId,   setIndexingId  ] = useState(null);

  useEffect(() => {
    function handleKey(e) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  useEffect(() => {
    if (tab !== "notes") return;
    fetchNotesFiles();
  }, [tab]);

  async function fetchNotesFiles() {
    setLoadingNotes(true);
    try {
      const res = await fetch(`/api/rag/notes-available?course_id=${courseId}`, {
        credentials: "include",
      });
      if (res.ok) setNotesFiles(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingNotes(false);
    }
  }

  async function handleLocalUpload() {
    if (!uploadFile) return;
    setUploading(true);
    setError("");
    const form = new FormData();
    form.append("file", uploadFile);
    form.append("course_id", courseId);
    try {
      const res = await fetch("/api/rag/upload", {
        method:      "POST",
        credentials: "include",
        body:        form,
      });
      if (!res.ok) {
        const text = await res.text();
        try {
          const err = JSON.parse(text);
          throw new Error(err.detail || "Upload failed");
        } catch {
          throw new Error(text || "Upload failed");
        }
      }
      onIndexed();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleIndexFromNotes(noteId) {
    setIndexingId(noteId);
    setError("");
    try {
      const res = await fetch("/api/rag/index-from-notes", {
        method:      "POST",
        credentials: "include",
        headers:     { "Content-Type": "application/json" },
        body:        JSON.stringify({ note_id: noteId, course_id: courseId }),
      });
      if (!res.ok) throw new Error("Failed to start indexing");
      onIndexed();
      onClose();
    } catch (err) {
      setError(err.message);
      setIndexingId(null);
    }
  }

  return (
    <div className={styles.modalOverlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <div>
            <div className={styles.modalTitle}>Add Files</div>
            <div className={styles.modalSubtitle}>{courseName}</div>
          </div>
          <button className={styles.modalClose} onClick={onClose}>
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>

        <div className={styles.modalTabs}>
          {[
            { key: "local", label: "From Computer", icon: "upload_file" },
            { key: "notes", label: "From Notes",    icon: "folder_open" },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`${styles.modalTab} ${tab === t.key ? styles.modalTabActive : ""}`}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 17 }}>{t.icon}</span>
              {t.label}
            </button>
          ))}
        </div>

        <div className={styles.modalBody}>
          {error && <div className={styles.modalError}>{error}</div>}

          {tab === "local" && (
            <>
              <label
                className={styles.dropzone}
                onDrop={e => { e.preventDefault(); setUploadFile(e.dataTransfer.files[0]); }}
                onDragOver={e => e.preventDefault()}
              >
                <span className={`material-symbols-outlined ${styles.dropzoneIcon}`}>cloud_upload</span>
                <div className={styles.dropzoneText}>
                  {uploadFile ? uploadFile.name : "Choose a file or drag and drop"}
                </div>
                <div className={styles.dropzoneHint}>PDF, DOCX, PPTX, TXT, MD</div>
                <input
                  type="file"
                  accept=".pdf,.docx,.pptx,.txt,.md"
                  style={{ display: "none" }}
                  onChange={e => setUploadFile(e.target.files[0])}
                />
              </label>
              <button
                className={styles.indexBtn}
                onClick={handleLocalUpload}
                disabled={!uploadFile || uploading}
              >
                {uploading ? "Indexing…" : "Index File"}
              </button>
            </>
          )}

          {tab === "notes" && (
            <div className={styles.notesList}>
              {loadingNotes ? (
                [1, 2, 3].map(i => <div key={i} className={styles.skeletonRow} />)
              ) : notesFiles.length === 0 ? (
                <div className={styles.emptyNotes}>
                  <span className={`material-symbols-outlined ${styles.emptyNotesIcon}`}>folder_off</span>
                  <div className={styles.emptyNotesText}>No unindexed notes found for this course</div>
                </div>
              ) : notesFiles.map(note => (
                <div key={note.note_id} className={styles.noteRow}>
                  <div className={styles.noteRowLeft}>
                    <span className={`material-symbols-outlined ${styles.noteRowIcon}`}>insert_drive_file</span>
                    <span className={styles.noteRowName}>{note.filename}</span>
                  </div>
                  {note.already_indexed ? (
                    <span className={styles.noteIndexedBadge}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>check_circle</span>
                      Indexed
                    </span>
                  ) : indexingId === note.note_id ? (
                    <span className={styles.noteIndexedBadge}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>pending</span>
                      Starting…
                    </span>
                  ) : (
                    <button
                      className={styles.noteIndexBtn}
                      onClick={() => handleIndexFromNotes(note.note_id)}
                      disabled={indexingId !== null}
                    >
                      Index
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AIPage() {
  const [isConnected,        setIsConnected       ] = useState(aiCache.isConnected ?? false);
  const [checkingConnection, setCheckingConnection] = useState(aiCache.courses === null);
  const [courses,            setCourses           ] = useState(aiCache.courses ?? []);
  const [courseId,           setCourseId          ] = useState("");
  const [messages,           setMessages          ] = useState([]);
  const [input,              setInput             ] = useState("");
  const [loading,            setLoading           ] = useState(false);
  const [streamingText,      setStreamingText     ] = useState("");
  const [error,              setError             ] = useState("");
  const [indexedFiles,       setIndexedFiles      ] = useState([]);
  const [uploadModalOpen,    setUploadModalOpen   ] = useState(false);
  const [filter,             setFilter            ] = useState("all");
  const [pastOpen,           setPastOpen          ] = useState(false);
  const bottomRef   = useRef(null);
  const textareaRef = useRef(null);

  const storageKey   = `sars_chat_history_${courseId}`;
  const course       = courses.find(c => c.id === courseId);
  const courseName   = course?.name || courseId;

  const currentCourses = courses.filter(c => c.is_current_term !== false);
  const pastCourses    = courses.filter(c => c.is_current_term === false);

  useEffect(() => { checkGoogleConnection(); }, []);

  useEffect(() => {
    if (!courseId) return;
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
    if (messages.length > 0)
      localStorage.setItem(storageKey, JSON.stringify(messages));
  }, [messages, courseId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  useEffect(() => {
    const hasProcessing = indexedFiles.some(f => f.indexing_status === "processing");
    if (!hasProcessing) return;
    const timer = setInterval(fetchIndexedFiles, 3000);
    return () => clearInterval(timer);
  }, [indexedFiles, courseId]);

  async function checkGoogleConnection() {
    setCheckingConnection(true);
    const controller = new AbortController();
    const timeout    = setTimeout(() => controller.abort(), 5000);
    try {
      const res  = await fetch("/api/auth/google/me", {
        credentials: "include",
        signal:      controller.signal,
      });
      if (!res.ok) { setIsConnected(false); aiCache.isConnected = false; return; }
      const data      = await res.json();
      const connected = Boolean(data.user && data.has_access_token);
      setIsConnected(connected);
      aiCache.isConnected = connected;
      if (connected) fetchCourses();
    } catch (err) {
      if (err.name !== "AbortError") console.error(err);
      setIsConnected(false);
      aiCache.isConnected = false;
    } finally {
      clearTimeout(timeout);
      setCheckingConnection(false);
    }
  }

  async function fetchCourses() {
    try {
      const res     = await fetch("/api/classroom/courses/upload-options", {
        credentials: "include",
        cache:       "no-store",
      });
      if (res.status === 401) { setIsConnected(false); return; }
      if (!res.ok) throw new Error("Failed to fetch courses");
      const data    = await res.json();
      const current = (data.current_courses || []).map(c => ({ ...c, is_current_term: true }));
      const past    = (data.past_courses || []).map(c => ({ ...c, is_current_term: false }));
      const fetched = [...current, ...past];
      aiCache.courses = fetched;
      setCourses(fetched);
      if (fetched.length > 0) setCourseId(fetched[0].id);
    } catch (err) {
      console.error(err);
    }
  }

  async function fetchIndexedFiles() {
    if (!courseId) return;
    try {
      const res = await fetch(`/api/rag/files?course_id=${courseId}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setIndexedFiles(data.files || []);
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleDeleteFile(filename, fileId) {
    if (!window.confirm(`Delete "${filename}" and all its indexed chunks?`)) return;
    try {
      const res = await fetch(`/api/rag/files/${fileId}?course_id=${courseId}`, {
        method:      "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        fetchIndexedFiles();
        setMessages(prev => [...prev, { role: "system", content: `Deleted ${filename}.` }]);
      }
    } catch (err) {
      setError(`Failed to delete: ${err.message}`);
    }
  }

  async function handleSendToNotes(fileId) {
    try {
      const res = await fetch("/api/rag/send-to-notes", {
        method:      "POST",
        credentials: "include",
        headers:     { "Content-Type": "application/json" },
        body:        JSON.stringify({ file_id: fileId, course_id: courseId }),
      });
      if (res.ok) {
        fetchIndexedFiles();
        setMessages(prev => [...prev, { role: "system", content: "Added file to Notes." }]);
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to add to Notes");
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleUpdateLabels(fileId, labels) {
    try {
      await fetch(`/api/rag/files/${fileId}/labels`, {
        method:      "PATCH",
        credentials: "include",
        headers:     { "Content-Type": "application/json" },
        body:        JSON.stringify({ labels }),
      });
      fetchIndexedFiles();
    } catch (err) {
      console.error(err);
    }
  }

  function defaultWelcome() {
    return {
      role:    "assistant",
      content: "Welcome to SARS AI. Upload course materials and ask questions about them.",
    };
  }

  function deduplicateCitations(citations) {
    if (!citations?.length) return [];
    const seen = new Set();
    return citations.filter(c => {
      const key = `${c.source}|${c.section}|${c.page}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;
    console.log("Chat payload:", { query: q, course_id: courseId, course_name: courseName });

    setMessages(prev => [...prev, { role: "user", content: q }]);
    setInput("");
    setLoading(true);
    setStreamingText("");
    setError("");

    if (textareaRef.current) textareaRef.current.style.height = "56px";

    try {
      const history = messages
        .filter(m => m.role !== "system")
        .map(m => ({ role: m.role, content: m.content }));

      const res = await fetch("/api/rag/chat", {
        method:      "POST",
        credentials: "include",
        headers:     { "Content-Type": "application/json" },
        body:        JSON.stringify({
          query:       q,
          course_id:   courseId,
          course_name: courseName,
          history,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let citations = [];
      let fullText  = "";

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
              throw new Error(event.error || "Unknown error");
          } catch (e) {
            if (e.message !== "Unknown error") console.error("SSE parse:", e);
            else throw e;
          }
        }
      }

      setMessages(prev => [...prev, { role: "assistant", content: fullText, citations }]);
      setStreamingText("");
    } catch (err) {
      setError(err.message);
      setMessages(prev => [...prev, {
        role:    "assistant",
        content: `Something went wrong: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  }

  const FILE_ICONS = {
    pdf:  { icon: "picture_as_pdf", color: "var(--color-error)"              },
    docx: { icon: "article",        color: "var(--color-primary)"            },
    pptx: { icon: "co_present",     color: "var(--color-tertiary)"           },
    txt:  { icon: "text_snippet",   color: "var(--color-on-surface-variant)" },
    md:   { icon: "text_snippet",   color: "var(--color-on-surface-variant)" },
  };

  function getFileIcon(filename) {
    const ext = filename?.split(".").pop()?.toLowerCase();
    return FILE_ICONS[ext] || { icon: "insert_drive_file", color: "var(--color-on-surface-variant)" };
  }

  const notInNotes   = indexedFiles.filter(f => !f.drive_file_id);
  const displayFiles = filter === "not_in_notes" ? notInNotes : indexedFiles;

  if (checkingConnection) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-on-surface-variant">Checking connection…</p>
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-8 gap-6">
        <div className="text-center">
          <h1 className="font-display text-4xl font-bold text-on-surface tracking-tight">AI Assistant</h1>
          <p className="text-sm text-on-surface-variant mt-2">Connect Google Classroom to get started</p>
        </div>
        <ConnectGoogleClassroomCard message="Connect Google Classroom to access your courses and use the AI assistant with your actual course materials." />
      </div>
    );
  }

  if (courses.length === 0) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-8 gap-4">
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 48, opacity: 0.3 }}>folder_off</span>
        <h2 className="text-xl font-semibold text-on-surface">No courses found</h2>
        <p className="text-sm text-on-surface-variant text-center max-w-sm">No active courses were found for this term in Google Classroom.</p>
        <button
          onClick={checkGoogleConnection}
          className="px-6 py-2 bg-primary text-on-primary rounded-full text-sm font-semibold transition hover:brightness-110"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className={styles.app}>

      {/* ── Course panel ── */}
      <div className={styles.coursePanel}>
        <div className={styles.coursePanelHeader}>Current Courses</div>
        <div className={styles.courseList}>

          {/* Current courses */}
          {currentCourses.map((c, i) => (
            <button
              key={c.id || i}
              onClick={() => setCourseId(c.id)}
              className={`${styles.courseItem} ${c.id === courseId ? styles.courseItemActive : ""}`}
            >
              <div className={styles.courseItemText}>
                <div className={styles.courseItemCode}>{c.name || "Untitled Course"}</div>
                <div className={styles.courseItemName}>{c.section || ""}</div>
              </div>
            </button>
          ))}

          {/* Past courses toggle */}
          {pastCourses.length > 0 && (
            <>
              <button
                className={styles.pastCoursesToggle}
                onClick={() => setPastOpen(o => !o)}
              >
                <span>Past Courses</span>
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                  {pastOpen ? "expand_less" : "expand_more"}
                </span>
              </button>

              {pastOpen && pastCourses.map((c, i) => (
                <button
                  key={c.id || i}
                  onClick={() => setCourseId(c.id)}
                  className={`${styles.courseItem} ${c.id === courseId ? styles.courseItemActive : ""}`}
                >
                  <div className={styles.courseItemText}>
                    <div className={styles.courseItemCode}>{c.name || "Untitled Course"}</div>
                    <div className={styles.courseItemName}>{c.section || ""}</div>
                  </div>
                </button>
              ))}
            </>
          )}

        </div>
      </div>

      {/* ── Chat panel ── */}
      <div className={styles.chatPanel}>
        <div className={styles.chatHeader}>
          <span
            className={`material-symbols-outlined ${styles.chatHeaderIcon}`}
            style={{ fontVariationSettings: '"FILL" 1' }}
          >
            smart_toy
          </span>
          <span className={styles.chatHeaderTitle}>SARS AI</span>
        </div>

        <div className={styles.messages}>
          <div className={styles.messagesInner}>

            {/* Empty state */}
            {messages.length === 1 && messages[0].role === "assistant" && (
              <div className={styles.emptyChat}>
                <div className={styles.emptyChatAvatar}>
                  <span className="material-symbols-outlined"
                    style={{ fontSize: 32, color: "var(--color-primary)", fontVariationSettings: '"FILL" 1' }}>
                    smart_toy
                  </span>
                </div>
                <h2 className={styles.emptyChatTitle}>SARS AI</h2>
                <p className={styles.emptyChatSubtitle}>Ask anything about your {courseName} materials</p>
              </div>
            )}

            {messages.map((msg, i) => {
              if (messages.length === 1 && msg.role === "assistant") return null;
              if (msg.role === "system") return (
                <div key={i} className={styles.systemMessage}>
                  <div className={styles.systemBubble}>{msg.content}</div>
                </div>
              );
              if (msg.role === "user") return (
                <div key={i} className={styles.userMessage}>
                  <div className={styles.userBubble}>{msg.content}</div>
                </div>
              );
              return (
                <div key={i} className={styles.aiBubble}>
                  <div className={styles.aiHeader}>
                    <div className={styles.aiAvatar}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--color-primary)", fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
                    </div>
                    <span className={styles.aiLabel}>SARS AI</span>
                  </div>
                  <div className={styles.aiText}>
                    {msg.content.split("\n\n").map((para, j) => <p key={j}>{para}</p>)}
                  </div>
                  {msg.citations?.length > 0 && (
                    <div className={styles.citations}>
                      {msg.citations.map((c, j) => (
                        <CitationChip
                          key={j}
                          citation={c}
                          indexedFiles={indexedFiles}
                          onUpdateLabels={handleUpdateLabels}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {loading && streamingText && (
              <div className={styles.aiBubble}>
                <div className={styles.aiHeader}>
                  <div className={styles.aiAvatar}>
                    <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--color-primary)", fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
                  </div>
                  <span className={styles.aiLabel}>SARS AI</span>
                </div>
                <div className={styles.aiText}>
                  {streamingText}
                  <span className={styles.cursor}>|</span>
                </div>
              </div>
            )}

            {loading && !streamingText && (
              <div className={styles.aiBubble}>
                <div className={styles.aiHeader}>
                  <div className={styles.aiAvatar}>
                    <span className="material-symbols-outlined" style={{ fontSize: 14, color: "var(--color-primary)", fontVariationSettings: '"FILL" 1' }}>smart_toy</span>
                  </div>
                  <span className={styles.aiLabel}>SARS AI</span>
                </div>
                <div className={styles.thinkingDots}>
                  {[0, 0.15, 0.3].map((d, i) => (
                    <div key={i} className={styles.dot} style={{ animationDelay: `${d}s` }} />
                  ))}
                </div>
              </div>
            )}

            <div ref={bottomRef} style={{ height: "180px", flexShrink: 0 }} />
          </div>
        </div>

        <div className={styles.inputArea}>
          <div className={styles.inputInner}>
            {error && <div className={styles.errorBanner}>{error}</div>}
            {indexedFiles.filter(f => f.indexing_status === "indexed").length === 0 && (
              <div className={styles.warningBanner}>
                No files indexed yet — upload materials using the panel on the right.
              </div>
            )}
            <div className={styles.inputBox}>
              <textarea
                ref={textareaRef}
                className={styles.textarea}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                onInput={e => {
                  e.target.style.height = "56px";
                  e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
                }}
                placeholder={`Ask about ${courseName}…`}
                disabled={loading}
              />
              <div className={styles.inputFooter}>
                <span className={styles.inputDisclaimer}>AI may provide inaccurate info.</span>
                <button
                  className={styles.sendBtn}
                  onClick={handleSend}
                  disabled={!input.trim() || loading}
                >
                  <span className={`material-symbols-outlined ${styles.sendIcon}`}>arrow_upward</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Files panel ── */}
      <div className={styles.filesPanel}>
        <div className={styles.filesPanelHeader}>
          <div className={styles.filesPanelTop}>
            <span className={styles.filesPanelTitle}>Project Files</span>
            <button className={styles.addBtn} onClick={() => setUploadModalOpen(true)}>
              <span className="material-symbols-outlined" style={{ fontSize: 22 }}>add_circle</span>
            </button>
          </div>
          <select
            className={styles.filterSelect}
            value={filter}
            onChange={e => setFilter(e.target.value)}
          >
            <option value="all">All Files ({indexedFiles.length})</option>
            <option value="not_in_notes">Not in Notes ({notInNotes.length})</option>
          </select>
        </div>

        <div className={styles.filesList}>
          {displayFiles.length === 0 ? (
            <div className={styles.emptyFiles}>
              <span className={`material-symbols-outlined ${styles.emptyFilesIcon}`}>folder_open</span>
              <div className={styles.emptyFilesText}>
                {filter === "not_in_notes" ? "All files are in Notes" : "No files indexed yet"}
              </div>
              {filter === "all" && (
                <button className={styles.emptyFilesBtn} onClick={() => setUploadModalOpen(true)}>
                  Upload your first file
                </button>
              )}
            </div>
          ) : displayFiles.map(f => {
            const { icon, color } = getFileIcon(f.filename);
            const isProcessing    = f.indexing_status === "processing";
            return (
              <div key={f.file_id} className={styles.fileRow}>
                <div className={styles.fileRowLeft}>
                  <span className={`material-symbols-outlined ${styles.fileIcon}`} style={{ color }}>
                    {icon}
                  </span>
                  <div className={styles.fileInfo}>
                    <div className={styles.fileName}>{f.filename}</div>
                    <div className={styles.fileStatus}>
                      {f.indexing_status === "indexed" && (
                        <>
                          <span className={`${styles.statusDot} ${styles.statusDotReady}`} />
                          <span className={`${styles.statusText} ${styles.statusTextReady}`}>Ready</span>
                        </>
                      )}
                      {f.indexing_status === "processing" && (
                        <>
                          <span className={`${styles.statusDot} ${styles.statusDotIndexing}`} />
                          <span className={`${styles.statusText} ${styles.statusTextIndexing}`}>Indexing</span>
                        </>
                      )}
                      {f.indexing_status === "failed" && (
                        <>
                          <span className={`${styles.statusDot} ${styles.statusDotFailed}`} />
                          <span className={`${styles.statusText} ${styles.statusTextFailed}`}>Retry</span>
                        </>
                      )}
                    </div>
                    {f.labels?.length > 0 && (
                      <div className={styles.fileLabels}>
                        {f.labels.slice(0, 2).map((label, i) => (
                          <span
                            key={i}
                            className={styles.fileLabel}
                            style={{ color: getLabelColor(label) }}
                          >
                            {label}
                          </span>
                        ))}
                        {f.labels.length > 2 && (
                          <span className={styles.fileLabel}>+{f.labels.length - 2}</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <div className={styles.fileActions}>
                  {!isProcessing && !f.drive_file_id && (
                    <button
                      className={styles.fileActionBtn}
                      onClick={() => handleSendToNotes(f.file_id)}
                      title="Add to Notes"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>note_add</span>
                    </button>
                  )}
                  {f.drive_file_id && (
                    <span
                      className={styles.fileActionBtn}
                      style={{ color: "var(--color-primary)", opacity: 0.4, cursor: "default" }}
                      title="Already in Notes"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>check_circle</span>
                    </span>
                  )}
                  <button
                    className={`${styles.fileActionBtn} ${styles.fileActionBtnDanger}`}
                    onClick={() => handleDeleteFile(f.filename, f.file_id)}
                    title={isProcessing ? "Cancel" : "Delete"}
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                      {isProcessing ? "close" : "delete"}
                    </span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {uploadModalOpen && (
        <UploadModal
          courseId={courseId}
          courseName={courseName}
          onClose={() => setUploadModalOpen(false)}
          onIndexed={() => fetchIndexedFiles()}
        />
      )}
    </div>
  );
}
