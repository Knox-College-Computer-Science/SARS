"use client";
import { useEffect, useState } from "react";
import ConnectGoogleClassroomCard from "../components/ConnectGoogleClassroomCard";

export default function NotesPage() {
  const [notes, setNotes] = useState([]);
  const [courses, setCourses] = useState([]);
  const [classroomMaterials, setClassroomMaterials] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState("All");
  const [isConnected, setIsConnected] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(true);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [loadingCourses, setLoadingCourses] = useState(false);
  const [loadingMaterials, setLoadingMaterials] = useState(false);
  const [previewNote, setPreviewNote] = useState(null);

  useEffect(() => {
    checkGoogleConnection();
  }, []);

  const checkGoogleConnection = async () => {
    setCheckingConnection(true);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const res = await fetch("http://localhost:8000/auth/google/me", {
        credentials: "include",
        signal: controller.signal,
      });

      if (!res.ok) {
        setIsConnected(false);
        return;
      }

      const data = await res.json();
      const connected = Boolean(data.user && data.has_access_token);
      setIsConnected(connected);

      if (connected) {
        fetchCourses();
        fetchNotes();
        fetchClassroomMaterialsData();
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Failed to check Google connection:", err);
      }
      setIsConnected(false);
    } finally {
      clearTimeout(timeout);
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
        setCourses([]);
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

  const fetchClassroomMaterialsData = async () => {
    setLoadingMaterials(true);
    try {
      const res = await fetch("http://localhost:8000/classroom/materials", {
        credentials: "include",
      });
      if (!res.ok) return;
      const data = await res.json();
      setClassroomMaterials(data.materials || []);
    } catch (err) {
      console.error("Failed to fetch classroom materials:", err);
    } finally {
      setLoadingMaterials(false);
    }
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
        <h1 className="text-4xl font-bold text-center mb-10">
          📁 Notes
        </h1>

        <div className="min-h-[60vh] flex items-center justify-center">
          <ConnectGoogleClassroomCard
            message="Connect Google Classroom to view your uploaded notes according to your current classes."
          />
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
              <a
                href={note.drive_view_link || `http://localhost:8000/files/${note.filename}`}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-[#555770] px-3 py-1 rounded text-sm hover:bg-gray-600 transition"
              >
                Open ↗
              </a>
            </div>
          </div>

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

      {/* Classroom Materials section */}
      <div className="mt-10">
        <h2 className="text-xl font-semibold mb-5">Classroom Materials</h2>

        {loadingMaterials && (
          <p className="text-gray-400 text-sm">Loading classroom materials...</p>
        )}

        {!loadingMaterials && classroomMaterials.length === 0 && (
          <p className="text-gray-500 text-sm">No classroom materials found for this term.</p>
        )}

        {!loadingMaterials && classroomMaterials.map((courseData) => (
          <div key={courseData.courseId} className="mb-8">
            <div className="flex items-center gap-2 mb-3 border-b border-gray-600 pb-2">
              <span className="text-base">📁</span>
              <h3 className="text-base font-semibold text-gray-200">{courseData.courseName}</h3>
            </div>

            {courseData.pdfs.length === 0 && courseData.slides.length === 0 && courseData.links.length === 0 && (
              <p className="ml-5 text-sm text-gray-500">No materials posted yet.</p>
            )}

            {courseData.pdfs.length > 0 && (
              <div className="ml-5 mb-4">
                <p className="text-xs text-gray-400 uppercase tracking-widest mb-2 font-semibold">PDFs</p>
                {courseData.pdfs.map((item, i) => (
                  <div key={i} className="bg-[#444654] p-4 mb-3 rounded-lg flex items-center justify-between">
                    <div>
                      <p className="font-medium">{item.title}</p>
                      <p className="text-sm text-gray-400">{courseData.courseName}</p>
                    </div>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-blue-500 px-3 py-1 rounded text-sm hover:bg-blue-600 transition"
                    >
                      View
                    </a>
                  </div>
                ))}
              </div>
            )}

            {courseData.slides.length > 0 && (
              <div className="ml-5 mb-4">
                <p className="text-xs text-gray-400 uppercase tracking-widest mb-2 font-semibold">Slides</p>
                {courseData.slides.map((item, i) => (
                  <div key={i} className="bg-[#444654] p-4 mb-3 rounded-lg flex items-center justify-between">
                    <div>
                      <p className="font-medium">{item.title}</p>
                      <p className="text-sm text-gray-400">{courseData.courseName}</p>
                    </div>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-blue-500 px-3 py-1 rounded text-sm hover:bg-blue-600 transition"
                    >
                      View
                    </a>
                  </div>
                ))}
              </div>
            )}

            {courseData.links.length > 0 && (
              <div className="ml-5 mb-4">
                <p className="text-xs text-gray-400 uppercase tracking-widest mb-2 font-semibold">Links</p>
                {courseData.links.map((item, i) => (
                  <div key={i} className="bg-[#444654] p-4 mb-3 rounded-lg flex items-center justify-between">
                    <div>
                      <p className="font-medium">{item.title}</p>
                      <p className="text-sm text-gray-400">{courseData.courseName}</p>
                    </div>
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-blue-500 px-3 py-1 rounded text-sm hover:bg-blue-600 transition"
                    >
                      View
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}