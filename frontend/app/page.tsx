"use client";
import { useEffect, useState } from "react";
import ConnectGoogleClassroomCard from "./components/ConnectGoogleClassroomCard";

type ClassroomAssignment = {
  id: string;
  courseId: string;
  courseName: string;
  title: string;
  dueDate?: {
    year: number;
    month: number;
    day: number;
  };
  dueTime?: {
    hours?: number;
    minutes?: number;
  };
  alternateLink?: string;
};

type ClassroomAnnouncement = {
  id: string;
  courseId: string;
  courseName: string;
  text: string;
  creationTime: string;
  updateTime?: string;
  alternateLink?: string;
};

function getDueDate(assignment: ClassroomAssignment) {
  if (!assignment.dueDate) return null;

  const { year, month, day } = assignment.dueDate;
  const hours = assignment.dueTime?.hours ?? 23;
  const minutes = assignment.dueTime?.minutes ?? 59;

  return new Date(year, month - 1, day, hours, minutes);
}

function getDaysLeft(dueDate: Date) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const due = new Date(dueDate);
  due.setHours(0, 0, 0, 0);

  const diffMs = due.getTime() - today.getTime();
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24));
}

function getAnnouncementDate(announcement: ClassroomAnnouncement) {
  return new Date(announcement.updateTime || announcement.creationTime);
}

function isWithinPastDays(date: Date, days: number) {
  const now = new Date();
  const cutoff = new Date();
  cutoff.setDate(now.getDate() - days);

  return date >= cutoff && date <= now;
}

function formatAnnouncementDate(date: Date) {
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function getDaysAgo(date: Date) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const postedDate = new Date(date);
  postedDate.setHours(0, 0, 0, 0);

  const diffMs = today.getTime() - postedDate.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

function getAnnouncementPreview(text: string, maxLength = 140) {
  const cleanText = text.replace(/\s+/g, " ").trim();

  if (cleanText.length <= maxLength) return cleanText;
  return cleanText.slice(0, maxLength).trim() + "...";
}

export default function Home() {
  const [assignments, setAssignments] = useState<ClassroomAssignment[]>([]);
  const [announcements, setAnnouncements] = useState<ClassroomAnnouncement[]>([]);
  const [loadingAssignments, setLoadingAssignments] = useState(true);
  const [loadingAnnouncements, setLoadingAnnouncements] = useState(true);
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    fetchDueSoonAssignments();
    fetchRecentAnnouncements();
  }, []);

  const fetchDueSoonAssignments = async () => {
    setLoadingAssignments(true);

    try {
      const res = await fetch("/api/classroom/assignments", {
        credentials: "include",
      });

      if (res.status === 401) {
        setIsConnected(false);
        setAssignments([]);
        return;
      }

      if (!res.ok) {
        throw new Error("Failed to fetch assignments");
      }

      const data = await res.json();
      const allAssignments: ClassroomAssignment[] = data.assignments || [];

      const dueSoon = allAssignments
        .filter((assignment) => {
          const dueDate = getDueDate(assignment);
          if (!dueDate) return false;

          const daysLeft = getDaysLeft(dueDate);
          return daysLeft >= 0 && daysLeft <= 7;
        })
        .sort((a, b) => {
          const dateA = getDueDate(a)?.getTime() ?? 0;
          const dateB = getDueDate(b)?.getTime() ?? 0;
          return dateA - dateB;
        });

      setAssignments(dueSoon);
      setIsConnected(true);
    } catch (err) {
      console.error("Failed to fetch due soon assignments:", err);
      setAssignments([]);
    } finally {
      setLoadingAssignments(false);
    }
  };

  const fetchRecentAnnouncements = async () => {
    setLoadingAnnouncements(true);

    try {
      const res = await fetch("/api/classroom/announcements", {
        credentials: "include",
      });

      if (res.status === 401) {
        setIsConnected(false);
        setAnnouncements([]);
        return;
      }

      if (!res.ok) {
        throw new Error("Failed to fetch announcements");
      }

      const data = await res.json();
      const allAnnouncements: ClassroomAnnouncement[] = data.announcements || [];

      const recentAnnouncements = allAnnouncements
        .filter((announcement) => {
          const announcementDate = getAnnouncementDate(announcement);
          return isWithinPastDays(announcementDate, 7);
        })
        .sort((a, b) => {
          const dateA = getAnnouncementDate(a).getTime();
          const dateB = getAnnouncementDate(b).getTime();
          return dateB - dateA;
        })
        .slice(0, 5);

      setAnnouncements(recentAnnouncements);
      setIsConnected(true);
    } catch (err) {
      console.error("Failed to fetch recent announcements:", err);
      setAnnouncements([]);
    } finally {
      setLoadingAnnouncements(false);
    }
  };

  return (
    <main className="p-8 text-white max-w-7xl mx-auto">
      {/* Welcome section */}
      <section className="text-center mb-10">
        <h1 className="text-4xl font-bold mb-3">Welcome to SARS</h1>
        <p className="text-gray-400 text-lg">
          Stay on top of your upcoming assignments and recent class updates.
        </p>
      </section>

      {/* Disconnected state */}
      {!isConnected ? (
        <div className="min-h-[60vh] flex items-center justify-center">
          <ConnectGoogleClassroomCard
            message="Connect Google Classroom to see assignments due soon and recent announcements from your current classes."
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Due Soon Assignments */}
          <section className="bg-[#202123] border border-gray-700 rounded-2xl p-6">
            <h2 className="text-2xl font-bold mb-5">🔔 Due This Week</h2>

            {loadingAssignments && (
              <p className="text-gray-400">Loading assignments...</p>
            )}

            {!loadingAssignments && assignments.length === 0 && (
              <p className="text-gray-400">No assignments due this week.</p>
            )}

            {!loadingAssignments && assignments.length > 0 && (
              <div className="space-y-4">
                {assignments.map((assignment) => {
                  const dueDate = getDueDate(assignment);
                  const daysLeft = dueDate ? getDaysLeft(dueDate) : null;

                  return (
                    <div
                      key={assignment.id}
                      className="bg-[#444654] rounded-xl p-5 flex items-center justify-between gap-4"
                    >
                      <div>
                        <h3 className="text-lg font-semibold">
                          {assignment.title}
                        </h3>
                        <p className="text-gray-400 text-sm">
                          {assignment.courseName}
                        </p>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        {daysLeft !== null && (
                          <span
                            className={`px-3 py-1 rounded-full font-semibold text-black text-sm ${
                              daysLeft <= 2 ? "bg-orange-400" : "bg-yellow-400"
                            }`}
                          >
                            {daysLeft === 0 ? "Due today" : `${daysLeft}d left`}
                          </span>
                        )}

                        {assignment.alternateLink && (
                          <a
                            href={assignment.alternateLink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg text-sm"
                          >
                            Open
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* Recent Announcements */}
          <section className="bg-[#202123] border border-gray-700 rounded-2xl p-6">
            <h2 className="text-2xl font-bold mb-5">📢 Recent Announcements</h2>

            {loadingAnnouncements && (
              <p className="text-gray-400">Loading announcements...</p>
            )}

            {!loadingAnnouncements && announcements.length === 0 && (
              <p className="text-gray-400">
                No announcements from the past 7 days.
              </p>
            )}

            {!loadingAnnouncements && announcements.length > 0 && (
              <div className="space-y-4">
                {announcements.map((announcement) => {
                  const announcementDate = getAnnouncementDate(announcement);
                  const daysAgo = getDaysAgo(announcementDate);

                  return (
                    <div
                      key={announcement.id}
                      className="bg-[#444654] rounded-xl p-5"
                    >
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div>
                          <h3 className="text-lg font-semibold">
                            {announcement.courseName}
                          </h3>
                          <p className="text-xs text-gray-400">
                            {formatAnnouncementDate(announcementDate)}
                          </p>
                        </div>



                        <div className="flex items-center gap-3 shrink-0">
                          <span className="px-3 py-1 rounded-full bg-purple-400 text-black text-sm font-semibold">
                            {daysAgo === 0 ? "Today" : `${daysAgo}d ago`}
                          </span>

                          {announcement.alternateLink && (
                            <a
                              href={announcement.alternateLink}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg text-sm"
                            >
                              Open
                            </a>
                          )}
                        </div>
                      </div>

                      <p className="text-gray-200 text-sm leading-relaxed">
                        {getAnnouncementPreview(announcement.text)}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}