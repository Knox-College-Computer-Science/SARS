"use client";
import { useEffect, useRef, useState } from "react";

const uploadCache = {
  courses: null,
};

export default function UploadBox() {
  const [file,           setFile          ] = useState(null);
  const [subject,        setSubject       ] = useState("");
  const [noteType,       setNoteType      ] = useState("Lecture Notes");
  const [loading,        setLoading       ] = useState(false);
  const [progress,       setProgress      ] = useState(0);
  const [lastResult,     setLastResult    ] = useState(null);
  const [courses,        setCourses       ] = useState(uploadCache.courses ?? []);
const [loadingCourses, setLoadingCourses] = useState(uploadCache.courses === null);
  const [previewUrl,     setPreviewUrl    ] = useState(null);
  const [dragActive,     setDragActive    ] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { fetchCourses(); }, []);

  async function fetchCourses() {
     // Skip if already cached
  if (uploadCache.courses !== null) {
    setCourses(uploadCache.courses);
    setLoadingCourses(false);
    return;
  }
    setLoadingCourses(true);
    try {
      const res = await fetch("/api/classroom/courses", { credentials: "include" });
      if (!res.ok) { setCourses([]); return; }
      const data = await res.json();
      setCourses(data.courses || []);
    } catch (err) {
      console.error(err);
      setCourses([]);
    } finally {
      setLoadingCourses(false);
    }
  }

  function handleFileSelect(f) {
    if (!f || f.type !== "application/pdf") return;
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
    setLastResult(null);
  }

  function removeFile() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleUpload() {
    if (!file || !subject) {
      alert("Please select a file and a course");
      return;
    }
    setLoading(true);
    setProgress(0);
    setLastResult(null);

    // Animate progress bar
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= 85) { clearInterval(interval); return p; }
        return p + Math.floor(Math.random() * 12) + 4;
      });
    }, 400);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject", subject);

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      const data = await res.json();
      clearInterval(interval);
      setProgress(100);
      if (!res.ok) { alert(data.detail || "Upload failed"); return; }
      setLastResult(data);
      removeFile();
      setSubject("");
    } catch {
      clearInterval(interval);
      alert("Upload failed — is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-8 relative overflow-hidden">
      {/* Atmospheric blobs */}
      <div className="absolute top-1/4 right-1/4 w-96 h-96 rounded-full pointer-events-none"
        style={{ background: "rgba(180,197,255,0.04)", filter: "blur(120px)" }} />
      <div className="absolute bottom-1/4 left-1/4 w-64 h-64 rounded-full pointer-events-none"
        style={{ background: "rgba(227,98,174,0.04)", filter: "blur(100px)" }} />

      <div className="w-full max-w-2xl bg-surface-container-low border border-outline-variant rounded-xl p-8 z-10">

        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="font-display text-4xl font-bold text-on-surface tracking-tight">
            Upload Academic Notes
          </h2>
          <p className="text-sm text-on-surface-variant mt-2">
            PDF only · Max 50MB · Indexed for AI Assistant
          </p>
        </div>

        {/* Drop zone */}
        {!previewUrl ? (
          <div
            onClick={() => inputRef.current?.click()}
            onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              handleFileSelect(e.dataTransfer.files[0]);
            }}
            className={`relative group cursor-pointer border-2 border-dashed rounded-lg p-8 flex flex-col items-center justify-center gap-4 mb-8 transition-all ${
              dragActive
                ? "border-primary bg-primary/5"
                : "border-outline-variant hover:border-primary bg-surface-container-lowest"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => handleFileSelect(e.target.files[0])}
            />
            <div className={`w-16 h-16 rounded-full flex items-center justify-center transition-transform ${
              dragActive ? "scale-110" : "group-hover:scale-110"
            }`} style={{ background: "rgba(180,197,255,0.1)" }}>
              <span className="material-symbols-outlined text-primary" style={{ fontSize: 36 }}>
                cloud_upload
              </span>
            </div>
            <div className="text-center">
              <p className="text-xl font-semibold text-on-surface">
                {dragActive ? "Drop your PDF here" : "Drag and drop your PDF here"}
              </p>
              <p className="text-xs text-on-surface-variant mt-1">Maximum file size: 50MB</p>
            </div>
            <button
              type="button"
              className="mt-1 px-5 py-2 bg-surface-container-highest text-on-surface text-sm font-bold rounded-lg border border-outline-variant hover:bg-surface-bright transition-colors"
            >
              Browse Files
            </button>
          </div>
        ) : (
          /* PDF Preview */
          <div className="mb-8 rounded-lg overflow-hidden border border-outline-variant">
            <div className="flex items-center justify-between px-4 py-2 bg-surface-container border-b border-outline-variant">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-error" style={{ fontSize: 16 }}>picture_as_pdf</span>
                <span className="text-xs text-on-surface-variant truncate max-w-[320px]">{file?.name}</span>
              </div>
              <button
                onClick={removeFile}
                className="text-xs text-on-surface-variant hover:text-error transition-colors flex items-center gap-1"
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>close</span>
                Remove
              </button>
            </div>
            <div className="bg-amber-950/30 border-b border-amber-900/50 px-4 py-2 flex items-start gap-2">
              <span className="material-symbols-outlined text-amber-400 mt-0.5" style={{ fontSize: 14 }}>warning</span>
              <p className="text-amber-300 text-xs leading-snug">
                Preview only — annotations made here won't be uploaded. Save edits first then re-select.
              </p>
            </div>
            <iframe src={previewUrl} title="PDF Preview" className="w-full" style={{ height: 400, border: "none" }} />
          </div>
        )}

        {/* Course + Note Type selects */}
        <div className="grid grid-cols-2 gap-6 mb-8">
          <div className="space-y-1">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider ml-1">
              Select Course
            </label>
            <div className="relative">
              <select
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-4 py-2.5 text-sm text-on-surface appearance-none outline-none focus:border-primary transition-colors"
              >
                <option value="">-- Choose a current class --</option>
                {loadingCourses && <option disabled>Loading courses…</option>}
                {courses.map((c) => (
                  <option key={c.id} value={c.name}>{c.name}</option>
                ))}
              </select>
              <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-on-surface-variant" style={{ fontSize: 18 }}>
                expand_more
              </span>
            </div>
            {!loadingCourses && courses.length === 0 && (
              <p className="text-amber-400 text-xs mt-1 ml-1">
                No courses found — try reconnecting Google Classroom.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider ml-1">
              Note Type
            </label>
            <div className="relative">
              <select
                value={noteType}
                onChange={(e) => setNoteType(e.target.value)}
                className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-4 py-2.5 text-sm text-on-surface appearance-none outline-none focus:border-primary transition-colors"
              >
                <option>Lecture Notes</option>
                <option>Research Paper</option>
                <option>Lab Report</option>
                <option>Textbook Chapter</option>
              </select>
              <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-on-surface-variant" style={{ fontSize: 18 }}>
                expand_more
              </span>
            </div>
          </div>
        </div>

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={loading || !file || !subject}
          className="w-full py-3 bg-primary text-on-primary text-base font-bold rounded-lg hover:brightness-110 active:scale-[0.98] transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ boxShadow: "0 4px 24px rgba(180,197,255,0.15)" }}
        >
          {loading ? (
            <>
              <span className="material-symbols-outlined animate-spin" style={{ fontSize: 20 }}>refresh</span>
              Processing…
            </>
          ) : lastResult ? (
            <>
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>check_circle</span>
              Upload Complete!
            </>
          ) : (
            <>
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>auto_awesome</span>
              Upload and Process
            </>
          )}
        </button>

        {/* Progress bar */}
        {loading && (
          <div className="mt-6 space-y-2">
            <div className="flex items-center justify-between text-xs font-bold">
              <span className="text-primary">Processing PDF…</span>
              <span className="text-on-surface-variant">{progress}%</span>
            </div>
            <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-on-surface-variant text-center italic">
              Uploading
            </p>
          </div>
        )}

        {/* Result card */}
        {lastResult && (
          <div className="mt-6 p-4 rounded-lg bg-surface-container border border-outline-variant space-y-2">
            <p className="text-sm font-semibold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-on-surface" style={{ fontSize: 16 }}>check_circle</span>
              {lastResult.message}
            </p>
            {lastResult.drive_view_link && (
              <a
                href={lastResult.drive_view_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <span className="material-symbols-outlined" style={{ fontSize: 13 }}>folder_open</span>
                View on Google Drive
                <span className="material-symbols-outlined" style={{ fontSize: 12 }}>open_in_new</span>
              </a>
            )}
          </div>
        )}

      </div>
    </div>
  );
}