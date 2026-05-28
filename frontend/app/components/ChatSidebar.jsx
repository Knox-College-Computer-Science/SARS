"use client";

import { useState, useEffect, useRef } from "react";
import styles from "./ChatSidebar.module.css";
import UserPickerModal from "./UserPickerModal";
import NewChannelModal from "./NewChannelModal";
import socket from "@/lib/socket";

const AVATAR_COLORS = [
  { bg: "#dcefe7", text: "#3e7a60" },
  { bg: "#efe2cc", text: "#90663a" },
  { bg: "#e0def8", text: "#6360a9" },
  { bg: "#d6e4f6", text: "#4671a8" },
];

const STATUS_CONFIG = {
  active:   { color: "#4ade80", label: "Active" },
  away:     { color: "#fbbf24", label: "Away" },
  inactive: { color: "#6b7280", label: "Inactive" },
};

function getAvatarColor(id = "") {
  const n = Array.from(id).reduce((s, c) => s + c.charCodeAt(0), 0);
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function ArchiveIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="21 8 21 21 3 21 3 8" />
      <rect x="1" y="3" width="22" height="5" />
      <line x1="10" y1="12" x2="14" y2="12" />
    </svg>
  );
}

export default function ChatSidebar({
  course,
  courses,
  channels,
  conversations,
  activeView,
  onSelectChannel,
  onSelectDM,
  onStartDM,
  onChannelCreated,
  onSelectCourse,
  currentUser,
  token,
  courseId,
  onlineUsers,
  userStatuses,
}) {
  const [showUserPicker,  setShowUserPicker]  = useState(false);
  const [showNewChannel,  setShowNewChannel]  = useState(false);
  const [myStatus,        setMyStatus]        = useState("active");
  const [showStatusMenu,  setShowStatusMenu]  = useState(false);
  const statusMenuRef = useRef(null);

  const isCurrentTerm = course?.is_current_term !== false;

  // Close status menu on outside click
  useEffect(() => {
    function handleClick(e) {
      if (statusMenuRef.current && !statusMenuRef.current.contains(e.target)) {
        setShowStatusMenu(false);
      }
    }
    if (showStatusMenu) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showStatusMenu]);

  function changeStatus(status) {
    setMyStatus(status);
    socket.emit("set_user_status", { status });
    setShowStatusMenu(false);
  }

  function getRecipientStatus(userId) {
    if (!onlineUsers?.has(userId)) return null;   // offline — no dot
    return userStatuses?.[userId] ?? "active";
  }

  const isChannelActive = (ch) =>
    activeView?.type === "channel" && activeView.channelId === ch.id;

  const isDMActive = (conv) =>
    activeView?.type === "dm" && activeView.conversationId === conv.id;

  return (
    <>
      <aside className={styles.sidebar}>
        <div className={styles.header}>
          {courses && courses.length > 1 ? (
            <select
              className={styles.courseSelect}
              value={course?.school_course_id ?? ""}
              onChange={(e) => {
                const selected = courses.find(c => c.school_course_id === e.target.value);
                if (selected && onSelectCourse) onSelectCourse(selected);
              }}
            >
              {courses.map(c => (
                <option key={c.school_course_id} value={c.school_course_id}>
                  {c.name}{c.is_current_term === false ? " (Archive)" : ""}
                </option>
              ))}
            </select>
          ) : (
            <div className={styles.courseName}>
              {course?.name ?? "Loading…"}
              {!isCurrentTerm && (
                <span className={styles.archiveBadge}>Archive</span>
              )}
            </div>
          )}
          <div className={styles.courseMeta}>
            {course?.course_code ?? course?.courseCode ?? ""}
            {course?.term ? ` · ${course.term}` : ""}
          </div>

          {currentUser && (
            <div className={styles.selfRow}>
              <div
                className={styles.selfAvatar}
                style={{
                  backgroundColor: getAvatarColor(currentUser.id).bg,
                  color:           getAvatarColor(currentUser.id).text,
                }}
              >
                {currentUser.initials}
              </div>
              <span className={styles.selfName}>{currentUser.name}</span>

              {/* Status picker */}
              <div className={styles.statusWrapper} ref={statusMenuRef}>
                <button
                  className={styles.statusDotBtn}
                  style={{ background: STATUS_CONFIG[myStatus].color }}
                  title={`Status: ${STATUS_CONFIG[myStatus].label} — click to change`}
                  onClick={() => setShowStatusMenu(m => !m)}
                />
                {showStatusMenu && (
                  <div className={styles.statusMenu}>
                    {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                      <button
                        key={key}
                        className={`${styles.statusOption} ${myStatus === key ? styles.statusOptionActive : ""}`}
                        onClick={() => changeStatus(key)}
                      >
                        <span className={styles.statusOptionDot} style={{ background: cfg.color }} />
                        {cfg.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <nav className={styles.nav}>
          <div className={styles.sectionRow}>
            <span className={styles.sectionLabel}>Channels</span>
            {isCurrentTerm && (
              <button
                className={styles.addBtn}
                title="New channel"
                onClick={() => setShowNewChannel(true)}
              >
                <PlusIcon />
              </button>
            )}
          </div>

          {!isCurrentTerm && (
            <div className={styles.archiveNotice}>
              <ArchiveIcon />
              <span>Read-only archive</span>
            </div>
          )}

          <div className={styles.list}>
            {channels.map((ch) => (
              <button
                key={ch.id}
                className={`${styles.channelBtn} ${isChannelActive(ch) ? styles.active : ""}`}
                onClick={() => onSelectChannel(ch)}
              >
                <span className={styles.hash}>#</span>
                <span className={styles.label}>{ch.name}</span>
                {ch.unread_count > 0 && (
                  <span className={styles.badge}>{ch.unread_count}</span>
                )}
              </button>
            ))}
          </div>

          <div className={styles.sectionRow} style={{ marginTop: 8 }}>
            <span className={styles.sectionLabel}>Direct Messages</span>
            <button
              className={styles.addBtn}
              title="New direct message"
              onClick={() => setShowUserPicker(true)}
            >
              <PlusIcon />
            </button>
          </div>

          <div className={styles.list}>
            {conversations.map((conv) => {
              const color = getAvatarColor(conv.recipient?.id ?? "");
              const recipientStatus = getRecipientStatus(conv.recipient?.id);
              return (
                <button
                  key={conv.id}
                  className={`${styles.dmBtn} ${isDMActive(conv) ? styles.active : ""}`}
                  onClick={() => onSelectDM(conv)}
                >
                  <div
                    className={styles.avatar}
                    style={{ backgroundColor: color.bg, color: color.text }}
                  >
                    {conv.recipient?.initials ?? "??"}
                  </div>
                  <div className={styles.dmInfo}>
                    <span className={styles.label}>{conv.recipient?.name ?? "Unknown"}</span>
                    {conv.last_message && (
                      <span className={styles.preview}>{conv.last_message}</span>
                    )}
                  </div>
                  {recipientStatus && (
                    <span
                      className={styles.onlineDot}
                      style={{ background: STATUS_CONFIG[recipientStatus]?.color ?? "#4ade80" }}
                      title={STATUS_CONFIG[recipientStatus]?.label ?? "Online"}
                    />
                  )}
                </button>
              );
            })}

            {conversations.length === 0 && (
              <p className={styles.emptyHint}>No conversations yet.</p>
            )}
          </div>
        </nav>
      </aside>

      {showUserPicker && (
        <UserPickerModal
          courseId={courseId}
          token={token}
          currentUser={currentUser}
          onSelect={(member) => {
            setShowUserPicker(false);
            onStartDM(member);
          }}
          onClose={() => setShowUserPicker(false)}
        />
      )}

      {showNewChannel && (
        <NewChannelModal
          courseId={courseId}
          token={token}
          onCreated={(ch) => {
            setShowNewChannel(false);
            onChannelCreated(ch);
          }}
          onClose={() => setShowNewChannel(false)}
        />
      )}
    </>
  );
}
