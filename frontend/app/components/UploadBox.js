"use client";
import { useState } from "react";

const SUBJECTS = [
  { group: "CS", options: ["CS 142", "CS 202", "CS 220", "CS 208", "CS 221", "CS 322"] },
  { group: "ECON", options: ["ECON 110", "ECON 120", "ECON 301", "ECON 302"] },
];

export default function UploadBox() {
  const [file, setFile] = useState(null);
  const [subject, setSubject] = useState("");
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    if (!file || !subject) {
      alert("Please select a file and a subject");
      return;
    }

    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject", subject);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      alert(data.message);
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
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        {/* Upload button */}
        <button
          onClick={handleUpload}
          disabled={loading}
          className="w-full bg-green-500 p-2 rounded hover:bg-green-600 text-white font-medium disabled:opacity-50 transition"
        >
          {loading ? "Uploading..." : "Upload"}
        </button>
      </div>
    </div>
  );
}