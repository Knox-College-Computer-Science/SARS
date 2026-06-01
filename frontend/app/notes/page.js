"use client";
import { useEffect, useState } from "react";
import NoteCard from "../components/NoteCard";
import ConnectGoogleClassroomCard from "../components/ConnectGoogleClassroomCard";

function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-highest ${className}`} />;
}

const notesCache = {
  notes:             null,
  courses:           null,
  classroomMaterials: null,
};

export default function NotesPage() {
  const [notes,              setNotes             ] = useState(notesCache.notes              ?? []);
  const [courses,            setCourses           ] = useState(notesCache.courses            ?? []);
  const [classroomMaterials, setClassroomMaterials] = useState(notesCache.classroomMaterials ?? []);
  const [selectedSubject,    setSelectedSubject   ] = useState("All");
  const [isConnected,        setIsConnected       ] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(true);
  const [loadingNotes,       setLoadingNotes      ] = useState(notesCache.notes              === null);
  const [loadingCourses,     setLoadingCourses    ] = useState(notesCache.courses            === null);
  const [loadingMaterials,   setLoadingMaterials  ] = useState(notesCache.classroomMaterials === null);
  const [previewNoteId,      setPreviewNoteId     ] = useState(null);

  useEffect(() => { checkGoogleConnection(); }, []);

  async function checkGoogleConnection() {
  setCheckingConnection(true);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const res  = await fetch("/api/auth/google/me", { credentials: "include", signal: controller.signal });
    if (!res.ok) {
      // Clear cache on disconnect
      notesCache.notes = null;
      notesCache.courses = null;
      notesCache.classroomMaterials = null;
      setIsConnected(false);
      return;
    }
    const data = await res.json();
    const connected = Boolean(data.user && data.has_access_token);
    setIsConnected(connected);
    if (connected) {
      if (notesCache.courses            === null) fetchCourses();
      if (notesCache.notes              === null) fetchNotes();
      if (notesCache.classroomMaterials === null) fetchClassroomMaterials();
    }
  } catch (err) {
    if (err.name !== "AbortError") console.error(err);
    setIsConnected(false);
  } finally {
    clearTimeout(timeout);
    setCheckingConnection(false);
  }
}

  async function fetchCourses() {
  setLoadingCourses(true);
  try {
    const res  = await fetch("/api/classroom/courses", { credentials: "include" });
    if (!res.ok) { notesCache.courses = []; setCourses([]); return; }
    const data = await res.json();
    notesCache.courses = data.courses || [];
    setCourses(notesCache.courses);
  } catch (err) {
    console.error(err); setCourses([]);
  } finally { setLoadingCourses(false); }
}

async function fetchNotes() {
  setLoadingNotes(true);
  try {
    const res  = await fetch("/api/notes", { credentials: "include" });
    const data = await res.json();
    const notes = Array.isArray(data) ? data : [];
    notesCache.notes = notes;
    setNotes(notes);
  } catch (err) {
    console.error(err);
    setNotes([]);
  } finally {
    setLoadingNotes(false);
  }
}

async function fetchClassroomMaterials() {
  setLoadingMaterials(true);
  try {
    const res  = await fetch("/api/classroom/materials", { credentials: "include" });
    if (!res.ok) return;
    const data = await res.json();
    notesCache.classroomMaterials = data.materials || [];
    setClassroomMaterials(notesCache.classroomMaterials);
  } catch (err) { console.error(err); }
  finally { setLoadingMaterials(false); }
}
  const filteredNotes = selectedSubject === "All"
    ? notes
    : notes.filter((n) => n.subject === selectedSubject);

  // ── Loading state ──────────────────────────────────────────────────────────
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

  // ── Not connected ──────────────────────────────────────────────────────────
  if (!isConnected) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-8 gap-6">
        <div className="text-center">
          <h1 className="font-display text-4xl font-bold text-on-surface tracking-tight">Notes</h1>
          <p className="text-sm text-on-surface-variant mt-2">Connect Google Classroom to view your notes</p>
        </div>
        <ConnectGoogleClassroomCard message="Connect Google Classroom to view your uploaded notes according to your current classes." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div>
        {/* Page header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-primary-container flex items-center justify-center">
              <span className="material-symbols-outlined text-on-primary" style={{ fontSize: 28 }}>folder</span>
            </div>
            <div>
              <h2 className="font-display text-4xl font-bold text-on-surface tracking-tight">Notes</h2>
              <p className="text-sm text-on-surface-variant mt-0.5">Your central repository for shared academic resources.</p>
            </div>
          </div>

          {/* Filter chips */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setSelectedSubject("All")}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
                selectedSubject === "All"
                  ? "bg-primary text-on-primary shadow-lg"
                  : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
              }`}
            >
              All
            </button>
            {loadingCourses ? (
              <Skeleton className="h-7 w-20 rounded-full" />
            ) : (
              courses.map((course) => (
                <button
                  key={course.id}
                  onClick={() => setSelectedSubject(course.name)}
                  className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${
                    selectedSubject === course.name
                      ? "bg-primary text-on-primary shadow-lg"
                      : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                  }`}
                >
                  {course.name}
                </button>
              ))
            )}
          </div>
        </div>

        {/* Uploaded notes list */}
<div className="space-y-3">
  {loadingNotes ? (
    <>
      <Skeleton className="h-16 rounded-lg" />
      <Skeleton className="h-16 rounded-lg" />
      <Skeleton className="h-16 rounded-lg" />
    </>
  ) : filteredNotes.length === 0 ? (
    <div className="bg-surface-container border border-outline-variant rounded-lg p-6 text-center">
      <span
        className="material-symbols-outlined text-on-surface-variant"
        style={{ fontSize: 32 }}
      >
        folder_off
      </span>

      <p className="text-sm text-on-surface-variant mt-2">
        No notes found for this class.
      </p>
    </div>
  ) : (
    filteredNotes.map((note) => (
      <div key={note.id}>
        <NoteCard
          note={note}
          isPreviewOpen={previewNoteId === note.id}
          onPreviewToggle={() =>
            setPreviewNoteId(
              previewNoteId === note.id ? null : note.id
            )
          }
        />

        {/* Inline PDF preview */}
        {previewNoteId === note.id && (
          <div className="bg-[#2d2f3e] rounded-b-lg overflow-hidden border-t border-white/5">
            <iframe
              src={
                note.drive_file_id
                  ? `https://drive.google.com/file/d/${note.drive_file_id}/preview`
                  : `/api/files/${note.filename}`
              }
              title={note.filename}
              className="w-full"
              style={{ height: "520px", border: "none" }}
            />
          </div>
        )}
      </div>
    ))
  )}
</div>

        {/* Classroom Materials */}
        {(loadingMaterials || classroomMaterials.filter(c => selectedSubject === "All" || c.courseName === selectedSubject).length > 0) && (
          <div className="mt-10">
            <h2 className="font-display text-2xl font-semibold text-on-surface mb-5 flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary" style={{ fontSize: 22 }}>class</span>
              Classroom Materials
            </h2>

            {loadingMaterials ? (
              <div className="space-y-3">
                <Skeleton className="h-14 rounded-lg" />
                <Skeleton className="h-14 rounded-lg" />
              </div>
            ) : (
             classroomMaterials
              .filter((courseData) => selectedSubject === "All" || courseData.courseName === selectedSubject)
              .map((courseData) => (
                <div key={courseData.courseId} className="mb-8">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-outline-variant">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>folder</span>
                    <h3 className="text-sm font-semibold text-on-surface">{courseData.courseName}</h3>
                  </div>

                  {courseData.pdfs.length === 0 && courseData.slides.length === 0 && courseData.links.length === 0 && (
                    <p className="ml-5 text-xs text-on-surface-variant">No materials posted yet.</p>
                  )}

                  {[
                    { label: "PDFs",   icon: "picture_as_pdf", items: courseData.pdfs,   color: "text-error"   },
                    { label: "Slides", icon: "co_present",     items: courseData.slides, color: "text-tertiary"},
                    { label: "Links",  icon: "link",           items: courseData.links,  color: "text-primary" },
                  ].map(({ label, icon, items, color }) =>
                    items.length > 0 ? (
                      <div key={label} className="ml-5 mb-4">
                        <p className={`text-[10px] font-bold uppercase tracking-widest mb-2 ${color}`}>{label}</p>
                        <div className="space-y-2">
                          {items.map((item, i) => (
                            <div key={i} className="bg-surface-container border border-outline-variant/30 hover:border-primary/40 rounded-lg p-3 flex items-center justify-between transition-all group">
                              <div className="flex items-center gap-3">
                                <span className={`material-symbols-outlined ${color}`} style={{ fontSize: 18 }}>{icon}</span>
                                <div>
                                  <p className="text-sm font-medium text-on-surface group-hover:text-primary transition-colors">{item.title}</p>
                                  <p className="text-xs text-on-surface-variant">{courseData.courseName}</p>
                                </div>
                              </div>
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-4 py-1.5 text-xs font-bold text-primary bg-primary/10 border border-primary/20 rounded-lg hover:bg-primary hover:text-on-primary transition-all flex items-center gap-1"
                              >
                                View
                                <span className="material-symbols-outlined" style={{ fontSize: 13 }}>open_in_new</span>
                              </a>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null
                  )}
                </div>
              ))
            )}
          </div>
        )}

      </div>

      {/* FAB — Upload shortcut */}
      <a
        href="/upload"
        className="fixed bottom-8 right-8 w-14 h-14 rounded-full bg-primary text-on-primary shadow-2xl flex items-center justify-center hover:scale-110 active:scale-95 transition-all z-50 group"
        aria-label="Upload new note"
      >
        <span className="material-symbols-outlined" style={{ fontSize: 28 }}>add</span>
        <span className="absolute right-full mr-3 bg-surface-container px-3 py-1.5 rounded-lg text-xs font-bold text-on-surface opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none border border-outline-variant">
          Upload new note
        </span>
      </a>
    </div>
  );
}