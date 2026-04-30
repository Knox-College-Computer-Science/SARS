"use client";
import { useEffect, useState } from "react";

export default function NotesPage() {
  const [notes, setNotes] = useState([]);
  const [courses, setCourses] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState("All");
  const [isConnected, setIsConnected] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(false);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [loadingCourses, setLoadingCourses] = useState(false);

  useEffect(() => {
    checkGoogleConnection();
  }, []);

  const checkGoogleConnection = async () => {
    setCheckingConnection(true);

    try {
      const res = await fetch("http://localhost:8000/auth/google/me", {
        credentials: "include",
      });

      if (!res.ok) {
        setIsConnected(false);
        return;
      }

      const data = await res.json();

      if (data.user && data.has_access_token) {
        setIsConnected(true);
        await fetchCourses();
        await fetchNotes();
      } else {
        setIsConnected(false);
      }
    } catch (err) {
      console.error("Failed to check Google connection:", err);
      setIsConnected(false);
    } finally {
      setCheckingConnection(false);
    }
  };

  const fetchCourses = async () => {
    setLoadingCourses(true);

    try {
      const res = await fetch("http://localhost:8000/classroom/courses", {
        credentials: "include",
      });

      if (res.status === 401) {
        setIsConnected(false);
        return;
      }

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

  const fetchNotes = async () => {
    setLoadingNotes(true);
    try {
      const res = await fetch("http://localhost:8000/notes", {
        credentials: "include",
      });
      const data = await res.json();
      setNotes(data);
    } catch (err) {
      console.error("Failed to fetch notes:", err);
    } finally {
      setLoadingNotes(false);
    }
  };

  const connectGoogleClassroom = () => {
    window.location.href = "http://localhost:8000/auth/google/login";
  };

  const filteredNotes =
    selectedSubject === "All"
      ? notes
      : notes.filter((n) => n.subject === selectedSubject);
  if (checkingConnection) {
    return (
      <div className="p-6 text-white">
        <p className="text-gray-400">Checking Google Classroom connection...</p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="p-6 text-white">
        <h1 className="text-2xl font-semibold mb-4">📂 Notes</h1>

        <div className="bg-[#2f3342] border border-gray-600 rounded-lg p-6 max-w-xl">
          <h2 className="text-xl font-semibold mb-2">
            Connect Google Classroom
          </h2>

          <p className="text-gray-300 mb-4">
            Connect to Google Classroom to upload and view notes according to
            your current classes.
          </p>

          <button
            onClick={connectGoogleClassroom}
            className="bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg text-sm font-medium"
          >
            Connect Google Classroom
          </button>
        </div>
      </div>
    );
  }
  
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

        {loadingCourses && (
          <span className="text-sm text-gray-400">Loading courses...</span>
        )}

        {!loadingCourses &&
          courses.map((course) => (
            <button
              key={course.id}
              onClick={() => setSelectedSubject(course.name)}
              className={`px-3 py-1 rounded-full text-sm ${
                selectedSubject === course.name
                  ? "bg-green-500"
                  : "bg-[#444654] hover:bg-gray-600"
              }`}
            >
              {course.name}
            </button>
          ))}
      </div>

      {/* Notes list */}
      {loadingNotes && <p className="text-gray-400">Loading notes...</p>}

      {!loadingNotes && filteredNotes.length === 0 && (
        <p className="text-gray-400">No notes found for this class.</p>
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