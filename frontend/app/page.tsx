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

export default function Home() {
  const [assignments, setAssignments] = useState<ClassroomAssignment[]>([]);
  const [loadingAssignments, setLoadingAssignments] = useState(true);
  const [isConnected, setIsConnected] = useState(true);

  useEffect(() => {
    fetchDueSoonAssignments();
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
    </div>
  );
}