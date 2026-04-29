"use client";
import { useState, useRef } from "react";

const SUBJECTS = [
  { group: "CS", options: ["CS 142", "CS 202", "CS 220", "CS 208", "CS 292", "CS 322"] },
  { group: "ECON", options: ["ECON 110", "ECON 120", "ECON 301", "ECON 302"] },
];

export default function UploadBox() {
  const [file, setFile] = useState(null);
  const [subject, setSubject] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const inputRef = useRef(null);


  const handleUpload = async () => {
    if (!file || !subject) {
      alert("Please select a file and a subject");
      return;
    }

    setLoading(true);
    setLastResult(null);

    const formData = new FormData();
    formData.append("file", file);   // uploads exactly what the user picked
    formData.append("subject", subject);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      setLastResult(data);
      setFile(null);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
      setSubject("");
    } catch (err) {
      alert("Upload failed — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="bg-[#444654] p-8 rounded-lg w-[800px] shadow-lg">
        <h2 className="text-xl mb-6 text-center text-white font-semibold">
          Upload Notes
        </h2>

        <label className="block text-gray-400 text-sm mb-2">Select PDF</label>
        <div
          onClick={() => inputRef.current?.click()}
          className="mb-5 w-full border-2 border-dashed border-gray-600 hover:border-green-400 rounded-lg p-4 cursor-pointer transition-colors flex items-center gap-3 bg-[#343541]"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="shrink-0">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <polyline points="14 2 14 8 20 8" stroke="#f87171" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div className="flex-1 min-w-0">
            {file ? (
              <p className="text-sm text-white truncate">{file.name}</p>
            ) : (
              <p className="text-sm text-gray-400">No file selected — click to browse</p>
            )}
          </div>
          <span className="text-xs bg-[#444654] border border-gray-600 px-3 py-1 rounded-full text-gray-300 hover:border-green-400 transition-colors shrink-0">
            Browse
          </span>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files[0];
            if (!f) return;
            setFile(f);
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            setPreviewUrl(URL.createObjectURL(f));
          }}
        />

        {/* PDF Preview — view only, edits here are NOT saved */}
        {previewUrl && (
          <div className="mb-5 rounded-lg overflow-hidden border border-gray-600">
            <div className="flex items-center justify-between px-3 py-2 bg-[#343541] border-b border-gray-600">
              <span className="text-xs text-gray-400 truncate">{file?.name}</span>
              <button
                onClick={() => { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); setFile(null); }}
                className="text-xs text-gray-500 hover:text-red-400 transition ml-2 shrink-0"
              >
                ✕ Remove
              </button>
            </div>
            {/* Warning banner */}
            <div className="bg-yellow-900/40 border-b border-yellow-700 px-3 py-2 flex items-start gap-2">
              <span className="text-yellow-400 text-xs mt-0.5">⚠️</span>
              <p className="text-yellow-300 text-xs leading-snug">
                This is a <strong>preview only</strong>. Any annotations made here won't be uploaded.
                To upload an edited PDF, save it first then re-select it.
              </p>
            </div>
            <iframe
              src={previewUrl}
              title="PDF Preview"
              className="w-full"
              style={{ height: "600px", border: "none" }}
            />
          </div>
        )}

        <label className="block text-gray-400 text-sm mb-1">Select Subject</label>
        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="w-full p-2 mb-6 rounded bg-[#343541] text-white outline-none border border-gray-600"
        >
          <option value="">-- Choose a subject --</option>
          {SUBJECTS.map((group) => (
            <optgroup key={group.group} label={group.group}>
              {group.options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </optgroup>
          ))}
        </select>

        <button
          onClick={handleUpload}
          disabled={loading}
          className="w-full bg-green-500 p-2 rounded hover:bg-green-600 text-white font-medium disabled:opacity-50 transition"
        >
          {loading ? "Uploading…" : "Upload"}
        </button>

        {lastResult && (
          <div className="mt-4 p-3 rounded bg-[#343541] text-sm">
            <p className="text-green-400 font-medium">{lastResult.message}</p>
            {lastResult.rag_indexed && (
              <p className="text-purple-400 mt-1 text-xs">
                🤖 Also indexed for AI Assistant — go to AI tab to ask questions!
              </p>
            )}
            {lastResult.rag_indexed === false && (
              <p className="text-yellow-500 mt-1 text-xs">
                ⚠️ AI indexing skipped (Ollama may not be running).
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}