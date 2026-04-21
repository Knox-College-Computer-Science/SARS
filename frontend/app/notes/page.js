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
            selectedSubject === "All"
              ? "bg-green-500"
              : "bg-[#444654] hover:bg-gray-600"
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
                selectedSubject === opt
                  ? "bg-green-500"
                  : "bg-[#444654] hover:bg-gray-600"
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
        <div
          key={note.id}
          className="bg-[#444654] p-4 mb-3 rounded-lg flex items-center justify-between"
        >
          <div>
            <p className="font-medium">{note.filename}</p>
            <p className="text-sm text-gray-400">{note.subject}</p>
            <p className="text-xs text-gray-500">{note.upload_time}</p>
          </div>

          <a
            href={`http://localhost:8000/files/${note.filename}`}
            target="_blank"
            className="bg-blue-500 px-3 py-1 rounded text-sm hover:bg-blue-600 transition"
          >
            View
          </a>
        </div>
      ))}
    </div>
  );
}