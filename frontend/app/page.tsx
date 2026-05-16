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
  return (
    <div>
      <ChatBox />
    </div>
  );
}