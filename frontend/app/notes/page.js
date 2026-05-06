"use client";
import { useEffect, useState } from "react";

const SUBJECTS = [
  { group: "CS", options: ["CS 142", "CS 202", "CS 220", "CS 208", "CS 221", "CS 322"] },
  { group: "ECON", options: ["ECON 110", "ECON 120", "ECON 301", "ECON 302"] },
];

export default function NotesPage() {
  const [notes, setNotes] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState("All");
  const [loading, setLoading] = useState(false);
  const [previewNote, setPreviewNote] = useState(null);  // ← NEW

  useEffect(() => {
    fetchNotes();
  }, []);

  const fetchNotes = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/notes");
      const data = await res.json();
      setNotes(data);
    } catch (err) {
      console.error("Failed to fetch notes");
    } finally {
      setLoading(false);
    }
  };

  const filteredNotes =
    selectedSubject === "All"
      ? notes
      : notes.filter((n) => n.subject === selectedSubject);

  return (
    <div className="p-6 text-white">
      <h1 className="text-2xl font-semibold mb-4">📂 Notes</h1>

      {/* Subject filter */}
      <div className="mb-5 flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedSubject("All")}
          className={`px-3 py-1 rounded-full text-sm ${
            selectedSubject === "All" ? "bg-green-500" : "bg-[#444654] hover:bg-gray-600"
          }`}
        >
          All
        </button>
        {SUBJECTS.map((group) =>
          group.options.map((opt) => (
            <button
              key={opt}
              onClick={() => setSelectedSubject(opt)}
              className={`px-3 py-1 rounded-full text-sm ${
                selectedSubject === opt ? "bg-green-500" : "bg-[#444654] hover:bg-gray-600"
              }`}
            >
              {opt}
            </button>
          ))
        )}
      </div>

      {/* Notes list */}
      {loading && <p className="text-gray-400">Loading...</p>}
      {!loading && filteredNotes.length === 0 && (
        <p className="text-gray-400">No notes found for this subject.</p>
      )}

      {filteredNotes.map((note) => (
        <div key={note.id} className="mb-3">
          <div className="bg-[#444654] p-4 rounded-lg flex items-center justify-between">
            <div>
              <p className="font-medium">{note.filename}</p>
              <p className="text-sm text-gray-400">{note.subject}</p>
              <p className="text-xs text-gray-500">{note.upload_time}</p>
              {note.uploaded_by && (
                <p className="text-xs text-gray-500">by {note.uploaded_by}</p>
              )}
            </div>

            <div className="flex items-center gap-2">
              {/* Preview toggle button */}
              <button
                onClick={() => setPreviewNote(previewNote?.id === note.id ? null : note)}
                className={`px-3 py-1 rounded text-sm transition ${
                  previewNote?.id === note.id
                    ? "bg-green-600 hover:bg-green-700"
                    : "bg-blue-500 hover:bg-blue-600"
                }`}
              >
                {previewNote?.id === note.id ? "Close" : "Preview"}
              </button>

              {/* Open in new tab */}
              <a
                href={note.drive_view_link || `http://localhost:8000/files/${note.filename}`}
                target="_blank"
                className="bg-[#555770] px-3 py-1 rounded text-sm hover:bg-gray-600 transition"
              >
                Open ↗
              </a>
            </div>
          </div>

          {/* Inline PDF preview — Drive or local fallback */}
          {previewNote?.id === note.id && (
            <div className="bg-[#2d2f3e] rounded-b-lg overflow-hidden border-t border-white/5">
              <iframe
                src={
                  note.drive_file_id
                    ? `https://drive.google.com/file/d/${note.drive_file_id}/preview`
                    : `http://localhost:8000/files/${note.filename}`
                }
                title={note.filename}
                className="w-full"
                style={{ height: "520px", border: "none" }}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}