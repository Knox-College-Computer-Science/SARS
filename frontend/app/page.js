"use client";

import { useEffect, useRef, useState } from "react";
import ConnectGoogleClassroomCard from "./components/ConnectGoogleClassroomCard";

function fetchOpts(extra = {}) {
  return { credentials: "include", ...extra };
}

function getDueDate(a) {
  if (!a.dueDate) return null;
  const { year, month, day } = a.dueDate;
  return new Date(year, month - 1, day, a.dueTime?.hours ?? 23, a.dueTime?.minutes ?? 59);
}
function getDaysLeft(d) {
  const today = new Date(); today.setHours(0,0,0,0);
  const due   = new Date(d); due.setHours(0,0,0,0);
  return Math.ceil((due.getTime() - today.getTime()) / 86_400_000);
}
function getAnnouncementDate(a) { return new Date(a.updateTime ?? a.creationTime); }
function isWithinPastDays(date, days) {
  const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - days);
  return date >= cutoff && date <= new Date();
}
function getDaysAgo(date) {
  const today = new Date(); today.setHours(0,0,0,0);
  const d = new Date(date); d.setHours(0,0,0,0);
  return Math.floor((today.getTime() - d.getTime()) / 86_400_000);
}
function getPreview(text, max = 100) {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length <= max ? clean : clean.slice(0, max).trim() + "…";
}

const hour = new Date().getHours();
const greeting = hour < 12 ? "Good Morning" : hour < 18 ? "Good Afternoon" : "Good Evening";

function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-lg bg-surface-container-highest ${className}`} />;
}

// ── Module-level cache — survives navigation, clears on full page refresh ──
const cache = {
  assignments:   null,
  announcements: null,
  todos:         null,
};

export default function Home() {
  // Initialise from cache so returning visitors see data immediately
  const [isConnected,          setIsConnected         ] = useState(null);
  const [assignments,          setAssignments         ] = useState(cache.assignments   ?? []);
  const [announcements,        setAnnouncements       ] = useState(cache.announcements ?? []);
  const [todos,                setTodos               ] = useState(cache.todos         ?? []);
  const [loadingAssignments,   setLoadingAssignments  ] = useState(cache.assignments   === null);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState(cache.announcements === null);
  const [loadingTodos,         setLoadingTodos        ] = useState(cache.todos         === null);
  const [newTask,              setNewTask             ] = useState("");
  const [category,             setCategory            ] = useState("Personal");
  const inputRef = useRef(null);

  useEffect(() => {
    checkConnection();
    // eslint-disable-next-line
  }, []);

  async function checkConnection() {
  // Always verify auth fresh — never cache this
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch("/api/auth/google/me", fetchOpts());
      if (res.ok) {
        setIsConnected(true);
        // Only fetch data if not already cached
        if (cache.assignments   === null) fetchAssignments();
        if (cache.announcements === null) fetchAnnouncements();
        if (cache.todos         === null) fetchTodos();
        return;
      } else {
        // Auth failed — clear all cached data too
        cache.assignments   = null;
        cache.announcements = null;
        cache.todos         = null;
        setIsConnected(false);
        return;
      }
    } catch {
      if (attempt === 0) {
        await new Promise((r) => setTimeout(r, 1000));
      } else {
        setIsConnected(false);
      }
    }
  }
}
  async function fetchAssignments() {
    setLoadingAssignments(true);
    try {
      const res = await fetch("/api/classroom/assignments", fetchOpts());
      if (!res.ok) throw new Error("Failed to fetch assignments");
      const data = await res.json();
      const dueSoon = (data.assignments || [])
        .filter((a) => { const d = getDueDate(a); return d && getDaysLeft(d) >= 0 && getDaysLeft(d) <= 7; })
        .sort((a, b) => (getDueDate(a)?.getTime() ?? 0) - (getDueDate(b)?.getTime() ?? 0));
      cache.assignments = dueSoon;
      setAssignments(dueSoon);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAssignments(false);
    }
  }

  async function fetchAnnouncements() {
    setLoadingAnnouncements(true);
    try {
      const res = await fetch("/api/classroom/announcements", fetchOpts());
      if (!res.ok) throw new Error("Failed to fetch announcements");
      const data = await res.json();
      const recent = (data.announcements || [])
        .filter((a) => isWithinPastDays(getAnnouncementDate(a), 7))
        .sort((a, b) => getAnnouncementDate(b).getTime() - getAnnouncementDate(a).getTime())
        .slice(0, 5);
      cache.announcements = recent;
      setAnnouncements(recent);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingAnnouncements(false);
    }
  }

  async function fetchTodos() {
    setLoadingTodos(true);
    try {
      const res = await fetch("/api/todos/", fetchOpts());
      if (!res.ok) throw new Error("Failed to fetch todos");
      const data = await res.json();
      cache.todos = data;
      setTodos(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingTodos(false);
    }
  }

  async function toggleTodo(id, currentDone) {
    const updated = todos.map((t) => (t.id === id ? { ...t, done: !t.done } : t));
    cache.todos = updated;
    setTodos(updated);
    try {
      const res = await fetch(`/api/todos/${id}`, fetchOpts({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ done: !currentDone }),
      }));
      if (!res.ok) throw new Error("Failed to update todo");
    } catch (err) {
      const reverted = todos.map((t) => (t.id === id ? { ...t, done: currentDone } : t));
      cache.todos = reverted;
      setTodos(reverted);
      console.error(err);
    }
  }

  async function addTodo() {
    if (!newTask.trim()) return;
    const tempId    = Date.now();
    const optimistic = { id: tempId, text: newTask.trim(), category, done: false };
    const withNew   = [...todos, optimistic];
    cache.todos = withNew;
    setTodos(withNew);
    setNewTask("");
    inputRef.current?.focus();
    try {
      const res = await fetch("/api/todos/", fetchOpts({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: optimistic.text, category }),
      }));
      if (!res.ok) throw new Error("Failed to add todo");
      const saved    = await res.json();
      const replaced = withNew.map((t) => (t.id === tempId ? saved : t));
      cache.todos = replaced;
      setTodos(replaced);
    } catch (err) {
      const rolled = withNew.filter((t) => t.id !== tempId);
      cache.todos = rolled;
      setTodos(rolled);
      console.error(err);
    }
  }

  async function deleteTodo(id) {
    const filtered = todos.filter((t) => t.id !== id);
    cache.todos = filtered;
    setTodos(filtered);
    try {
      const res = await fetch(`/api/todos/${id}`, fetchOpts({ method: "DELETE" }));
      if (!res.ok) throw new Error("Failed to delete todo");
    } catch (err) {
      fetchTodos();
      console.error(err);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (isConnected === null) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-on-surface-variant">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center px-8">
        <ConnectGoogleClassroomCard message="Connect Google Classroom to see assignments due soon and recent announcements from your current classes." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-on-surface">
      <div className="p-6 grid grid-cols-12 gap-4">

        <div className="col-span-9 flex flex-col gap-5">
          <div className="relative rounded-xl bg-surface-container border border-outline-variant p-6 min-h-[148px] flex flex-col justify-center overflow-hidden">
            <div className="pointer-events-none absolute inset-0 opacity-[0.03]"
              style={{ backgroundImage: "radial-gradient(circle, #b4c5ff 1px, transparent 1px)", backgroundSize: "24px 24px" }} />
            <h2 className="font-display text-4xl font-bold text-on-surface tracking-tight">{greeting}</h2>
            {loadingAssignments ? (
              <Skeleton className="mt-2 h-5 w-72" />
            ) : (
              <p className="mt-2 text-primary font-medium text-base">
                {assignments.length > 0
                  ? `You have ${assignments.length} assignment${assignments.length !== 1 ? "s" : ""} due this week.`
                  : "You're all caught up — no assignments due this week! 🎉"}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-5">
            <section className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-xl font-semibold flex items-center gap-2">
                  <span className="material-symbols-outlined text-error" style={{ fontSize: 20 }}>assignment_late</span>
                  Due This Week
                </h3>
                <button className="text-xs text-primary hover:underline">View All</button>
              </div>
              {loadingAssignments ? (
                <div className="space-y-3">
                  <Skeleton className="h-28 rounded-xl" />
                  <Skeleton className="h-24 rounded-xl" />
                </div>
              ) : assignments.length === 0 ? (
                <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4 text-on-surface-variant text-sm">
                  No assignments due this week.
                </div>
              ) : (
                <div className="space-y-3">
                  {assignments.map((assignment) => {
                    const dueDate  = getDueDate(assignment);
                    const daysLeft = dueDate ? getDaysLeft(dueDate) : null;
                    const isUrgent = daysLeft !== null && daysLeft <= 2;
                    return (
                      <div key={assignment.id}
                        className="bg-surface-container-low border border-outline-variant rounded-xl p-4 flex flex-col gap-2 hover:bg-surface-container transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                            isUrgent ? "bg-secondary-container text-on-secondary-container" : "bg-surface-container-highest text-on-surface-variant"
                          }`}>
                            {isUrgent ? "Urgent" : "Standard"}
                          </span>
                          <span className={`text-xs font-bold ${isUrgent ? "text-error" : "text-on-surface-variant"}`}>
                            {daysLeft === 0 ? "Due today" : daysLeft !== null ? `${daysLeft}d left` : ""}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-on-surface">{assignment.title}</h4>
                        <p className="text-sm text-on-surface-variant">{assignment.courseName}</p>
                        {assignment.alternateLink && (
                          <a href={assignment.alternateLink} target="_blank" rel="noopener noreferrer"
                            className="mt-1 self-start flex items-center gap-1 text-xs font-semibold bg-primary-container text-on-primary px-3 py-1 rounded-lg hover:opacity-90 transition-opacity"
                          >
                            Open
                            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>arrow_forward</span>
                          </a>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-xl font-semibold flex items-center gap-2">
                  <span className="material-symbols-outlined text-tertiary" style={{ fontSize: 20 }}>campaign</span>
                  Recent Announcements
                </h3>
              </div>
              {loadingAnnouncements ? (
                <div className="rounded-xl overflow-hidden border border-outline-variant space-y-px">
                  <Skeleton className="h-16 rounded-none" />
                  <Skeleton className="h-16 rounded-none" />
                  <Skeleton className="h-16 rounded-none" />
                </div>
              ) : announcements.length === 0 ? (
                <div className="bg-surface-container border border-outline-variant rounded-xl p-4 text-on-surface-variant text-sm">
                  No announcements from the past 7 days.
                </div>
              ) : (
                <div className="bg-surface-container rounded-xl overflow-hidden border border-outline-variant">
                  {announcements.map((ann, idx) => {
                    const daysAgo = getDaysAgo(getAnnouncementDate(ann));
                    return (
                      <div key={ann.id}
                        className={`p-3 hover:bg-surface-container-high transition-colors cursor-pointer group ${idx < announcements.length - 1 ? "border-b border-outline-variant" : ""}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-tertiary">{ann.courseName}</span>
                          <span className="text-xs text-on-surface-variant">
                            {daysAgo === 0 ? "Today" : `${daysAgo}d ago`}
                          </span>
                        </div>
                        <p className="text-xs font-bold text-on-surface group-hover:text-primary transition-colors">
                          {getPreview(ann.text, 80)}
                        </p>
                        {ann.alternateLink && (
                          <a href={ann.alternateLink} target="_blank" rel="noopener noreferrer"
                            className="mt-1 inline-flex items-center gap-0.5 text-xs text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            Open
                            <span className="material-symbols-outlined" style={{ fontSize: 13 }}>open_in_new</span>
                          </a>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        </div>

        <div className="col-span-3">
          <div className="sticky top-6 flex flex-col gap-3 bg-surface-container-low border border-outline-variant rounded-xl p-4 max-h-[calc(100vh-48px)]">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-base font-semibold flex items-center gap-2">
                <span className="material-symbols-outlined text-secondary" style={{ fontSize: 20 }}>checklist</span>
                Quick To-Do
              </h3>
              <span className="text-xs text-on-surface-variant">
                {todos.filter((t) => t.done).length}/{todos.length} done
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1 pr-0.5">
              {loadingTodos ? (
                <>
                  <Skeleton className="h-10 rounded-lg" />
                  <Skeleton className="h-10 rounded-lg" />
                  <Skeleton className="h-10 rounded-lg" />
                </>
              ) : todos.length === 0 ? (
                <p className="text-xs text-on-surface-variant text-center py-6">No tasks yet — add one below!</p>
              ) : (
                todos.map((todo) => (
                  <div key={todo.id} className="flex items-start gap-3 p-2 rounded-lg hover:bg-surface-container group transition-colors">
                    <div
                      onClick={() => toggleTodo(todo.id, todo.done)}
                      className={`mt-0.5 w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center cursor-pointer transition-colors ${
                        todo.done ? "bg-primary border-primary" : "border-outline-variant group-hover:border-primary"
                      }`}
                    >
                      {todo.done && <span className="material-symbols-outlined text-on-primary" style={{ fontSize: 14 }}>check</span>}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm font-medium transition-all ${todo.done ? "line-through opacity-40" : "text-on-surface"}`}>
                        {todo.text}
                      </p>
                      <span className={`text-xs text-on-surface-variant ${todo.done ? "opacity-40" : ""}`}>{todo.category}</span>
                    </div>
                    <button
                      onClick={() => deleteTodo(todo.id)}
                      className="opacity-0 group-hover:opacity-100 text-on-surface-variant hover:text-error transition-all flex-shrink-0 mt-0.5"
                      aria-label="Delete task"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>close</span>
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="border-t border-outline-variant pt-3 space-y-2">
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-surface-container-high border border-outline-variant rounded-lg px-3 py-1.5 text-xs text-on-surface-variant outline-none focus:border-primary transition-colors"
              >
                <option>Personal</option>
                <option>Academic</option>
                <option>Coursework</option>
                <option>Study</option>
              </select>
              <div className="flex items-center gap-2 bg-surface-container-high rounded-lg px-3 py-2">
                <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 18 }}>add</span>
                <input
                  ref={inputRef}
                  value={newTask}
                  onChange={(e) => setNewTask(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addTodo()}
                  placeholder="Add new task…"
                  className="flex-1 bg-transparent border-none outline-none text-sm text-on-surface placeholder:text-on-surface-variant"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}