"use client";
import { useEffect, useState } from "react";

export default function UploadBox() {
  const [file, setFile] = useState(null);
  const [subject, setSubject] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [courses, setCourses] = useState([]);
  const [loadingCourses, setLoadingCourses] = useState(false);

  useEffect(() => {
    fetchCourses();
  }, []);

  const fetchCourses = async () => {
    setLoadingCourses(true);

    try {
      const res = await fetch("http://localhost:8000/classroom/courses", {
        credentials: "include",
      });

      if (!res.ok) {
        throw new Error("Failed to fetch courses");
      }

      const data = await res.json();
      setCourses(data.courses || []);
    } catch (err) {
      console.error("Failed to fetch courses:", err);
      setCourses([]);
    } finally {
      setLoadingCourses(false);
    }
  };


  const handleUpload = async () => {
    if (!file || !subject) {
      alert("Please select a file and a subject");
      return;
    }

    setLoading(true);
    setLastResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject", subject);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      const data = await res.json();
      setLastResult(data);
      setFile(null);
      setSubject("");
    } catch (err) {
      alert("Upload failed — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="bg-[#444654] p-8 rounded-lg w-[420px] shadow-lg">
        <h2 className="text-xl mb-6 text-center text-white font-semibold">
          Upload Notes
        </h2>

        {/* File input */}
        <label className="block text-gray-400 text-sm mb-1">Select PDF</label>
        <input
          type="file"
          accept=".pdf"
          className="mb-5 w-full text-sm text-white"
          onChange={(e) => setFile(e.target.files[0])}
        />

        {/* Subject dropdown */}
        <label className="block text-gray-400 text-sm mb-1">Select Class</label>
        <select
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          className="w-full p-2 mb-6 rounded bg-[#343541] text-white outline-none border border-gray-600"
        >
          <option value="">-- Choose a current class --</option>

          {loadingCourses && (
            <option value="" disabled>
              Loading courses...
            </option>
          )}

          {!loadingCourses &&
            courses.map((course) => (
              <option key={course.id} value={course.name}>
                {course.name}
              </option>
            ))}
        </select>

        {!loadingCourses && courses.length === 0 && (
          <p className="text-yellow-400 text-xs mb-4">
            No current-term courses found. Try reconnecting Google Classroom.
          </p>
        )}

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={loading}
          className="w-full bg-green-500 p-2 rounded hover:bg-green-600 text-white font-medium disabled:opacity-50 transition"
        >
          {loading ? "Uploading…" : "Upload"}
        </button>

        {/* Result feedback */}
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
