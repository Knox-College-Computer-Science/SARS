"use client";
import { useEffect, useState } from "react";
import ChatBox from "./components/ChatBox";

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

function getAnnouncementPreview(text: string, maxLength = 160) {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + "...";
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
      const res = await fetch("http://localhost:8000/classroom/assignments", {
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
      const res = await fetch("http://localhost:8000/classroom/announcements", {
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
    <div className="p-8 text-white">
      <section className="max-w-3xl mx-auto mb-10">
        <h1 className="text-3xl font-bold mb-6">🔔 Due This Week</h1>

        {!isConnected && (
          <div className="bg-[#444654] rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-2">
              Connect Google Classroom
            </h2>
            <p className="text-gray-300 mb-4">
              Connect Google Classroom to see assignments due soon.
            </p>
            <a
              href="/connect"
              className="inline-block bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg"
            >
              Go to Connect Page
            </a>
          </div>
        )}

        {isConnected && loadingAssignments && (
          <p className="text-gray-400">Loading assignments...</p>
        )}

        {isConnected && !loadingAssignments && assignments.length === 0 && (
          <p className="text-gray-400">No assignments due this week.</p>
        )}

        {isConnected && !loadingAssignments && assignments.length > 0 && (
          <div className="space-y-4">
            {assignments.map((assignment) => {
              const dueDate = getDueDate(assignment);
              const daysLeft = dueDate ? getDaysLeft(dueDate) : null;

              return (
                <div
                  key={assignment.id}
                  className="bg-[#444654] rounded-xl p-5 flex items-center justify-between"
                >
                  <div>
                    <h2 className="text-xl font-semibold">
                      {assignment.title}
                    </h2>
                    <p className="text-gray-400">{assignment.courseName}</p>
                  </div>

                  <div className="flex items-center gap-4">
                    {daysLeft !== null && (
                      <span
                        className={`px-3 py-1 rounded-full font-semibold text-black ${
                          daysLeft <= 2 ? "bg-orange-400" : "bg-yellow-400"
                        }`}
                      >
                        {daysLeft === 0
                          ? "Due today"
                          : `${daysLeft}d left`}
                      </span>
                    )}

                    {assignment.alternateLink && (
                      <a
                        href={assignment.alternateLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg"
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

      <ChatBox />
      <section className="max-w-3xl mx-auto mb-10">
        <h1 className="text-3xl font-bold mb-6">📢 Recent Announcements</h1>

        {!isConnected && (
          <div className="bg-[#444654] rounded-xl p-6">
            <h2 className="text-xl font-semibold mb-2">
              Connect Google Classroom
            </h2>
            <p className="text-gray-300 mb-4">
              Connect Google Classroom to see recent class announcements.
            </p>
            <a
              href="/connect"
              className="inline-block bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg"
            >
              Go to Connect Page
            </a>
          </div>
        )}

        {isConnected && loadingAnnouncements && (
          <p className="text-gray-400">Loading announcements...</p>
        )}

        {isConnected && !loadingAnnouncements && announcements.length === 0 && (
          <p className="text-gray-400">No announcements from the past 7 days.</p>
        )}

        {isConnected && !loadingAnnouncements && announcements.length > 0 && (
          <div className="space-y-4">
            {announcements.map((announcement) => {
              const announcementDate = getAnnouncementDate(announcement);

              return (
                <div
                  key={announcement.id}
                  className="bg-[#444654] rounded-xl p-5"
                >
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <div>
                      <h2 className="text-lg font-semibold">
                        {announcement.courseName}
                      </h2>
                      <p className="text-xs text-gray-400">
                        {formatAnnouncementDate(announcementDate)}
                      </p>
                    </div>

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

                  <p className="text-gray-200 whitespace-pre-line">
                    {getAnnouncementPreview(announcement.text)}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}