"use client";

import { useState } from "react";
import styles from "./ChatSidebar.module.css";
import UserPickerModal from "./UserPickerModal";
import NewChannelModal from "./NewChannelModal";

const AVATAR_COLORS = [
  { bg: "#dcefe7", text: "#3e7a60" },
  { bg: "#efe2cc", text: "#90663a" },
  { bg: "#e0def8", text: "#6360a9" },
  { bg: "#d6e4f6", text: "#4671a8" },
];

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

export default function ChatSidebar({
  course,
  channels,
  conversations,
  activeView,
  onSelectChannel,
  onSelectDM,
  onStartDM,
  onChannelCreated,
  currentUser,
  token,
  courseId,
  onlineUsers,
}) {
  const [showUserPicker, setShowUserPicker] = useState(false);
  const [showNewChannel, setShowNewChannel] = useState(false);

  const isChannelActive = (ch) =>
    activeView?.type === "channel" && activeView.channelId === ch.id;

  const isDMActive = (conv) =>
    activeView?.type === "dm" && activeView.conversationId === conv.id;

  return (
    <>
      <aside className={styles.sidebar}>
        <div className={styles.header}>
          <div className={styles.courseName}>{course?.name ?? "Loading…"}</div>
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
              <span className={styles.onlineDot} title="Online" />
            </div>
          )}
        </div>

        <nav className={styles.nav}>
          <div className={styles.sectionRow}>
            <span className={styles.sectionLabel}>Channels</span>
            <button
              className={styles.addBtn}
              title="New channel"
              onClick={() => setShowNewChannel(true)}
            >
              <PlusIcon />
            </button>
          </div>

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
              const online = onlineUsers?.has(conv.recipient?.id);
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
                  {online && <span className={styles.onlineDot} title="Online" />}
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
