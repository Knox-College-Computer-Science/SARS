"use client";

import { useState } from "react";
import styles from "./Message.module.css";

const AVATAR_COLORS = [
  { bg: "#2a3a32", text: "#7ab898" },
  { bg: "#3a3020", text: "#c4965a" },
  { bg: "#2a2848", text: "#9996d8" },
  { bg: "#1e2e40", text: "#6e9ec8" },
];
const OWN_AVATAR = { bg: "#243040", text: "#7aaad8" };
const QUICK_EMOJIS = ["👍", "❤️", "😂", "😮", "😢", "🔥"];

function getAvatarColor(id = "") {
  const n = Array.from(id).reduce((s, c) => s + c.charCodeAt(0), 0);
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function SmileIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M8 13s1.5 2 4 2 4-2 4-2" />
      <line x1="9" y1="9" x2="9.01" y2="9" />
      <line x1="15" y1="9" x2="15.01" y2="9" />
    </svg>
  );
}

function PencilIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

function EditBox({ initial, onSave, onCancel }) {
  const [val, setVal] = useState(initial);
  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSave(val); }
    if (e.key === "Escape") onCancel();
  }
  return (
    <div className={styles.editBox}>
      <textarea
        className={styles.editInput}
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={handleKey}
        autoFocus
        rows={2}
      />
      <div className={styles.editHint}>
        <kbd>Enter</kbd> to save · <kbd>Esc</kbd> to cancel
      </div>
    </div>
  );
}

export default function Message({
  msg,
  isOwn,
  currentUser,
  onReact,
  onEdit,
  onDelete,
  compact,
}) {
  const [editing,    setEditing]    = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const avatarColor = isOwn ? OWN_AVATAR : getAvatarColor(msg.senderId);

  function handleSaveEdit(newContent) {
    if (newContent.trim() && newContent.trim() !== msg.content) {
      onEdit?.(msg.id, newContent.trim());
    }
    setEditing(false);
  }

  const reactionEntries = Object.entries(msg.reactions ?? {});
  const showActions = !editing && (onReact || (isOwn && (onEdit || onDelete)));

  return (
    <article className={`${styles.root} ${compact ? styles.compact : ""}`}>
      {!compact ? (
        <div
          className={styles.avatar}
          style={{ backgroundColor: avatarColor.bg, color: avatarColor.text }}
        >
          {msg.senderInitials}
        </div>
      ) : (
        <div className={styles.avatarPlaceholder} />
      )}

      <div className={styles.body}>
        {!compact && (
          <div className={styles.meta}>
            <span className={`${styles.name} ${isOwn ? styles.ownName : ""}`}>
              {isOwn ? "You" : msg.senderName}
            </span>
            <span className={styles.time}>{formatTime(msg.sentAt)}</span>
            {msg.editedAt && <span className={styles.edited}>(edited)</span>}
          </div>
        )}

        {editing ? (
          <EditBox
            initial={msg.content}
            onSave={handleSaveEdit}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <p className={styles.text}>{msg.content}</p>
        )}

        {reactionEntries.length > 0 && (
          <div className={styles.reactions}>
            {reactionEntries.map(([emoji, data]) => {
              const iMine = data.users?.includes(currentUser?.id);
              return (
                <button
                  key={emoji}
                  className={`${styles.pill} ${iMine ? styles.pillMine : ""}`}
                  onClick={() => onReact?.(msg.id, emoji)}
                  title={`${data.count} reaction${data.count !== 1 ? "s" : ""}`}
                >
                  {emoji} {data.count}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {showActions && (
        <div className={styles.actions}>
          {onReact && (
            <div className={styles.emojiTriggerWrap}>
              <button
                className={styles.actionBtn}
                title="React"
                onClick={() => setPickerOpen(p => !p)}
              >
                <SmileIcon />
              </button>
              {pickerOpen && (
                <div className={styles.emojiPicker}>
                  {QUICK_EMOJIS.map(e => (
                    <button
                      key={e}
                      className={styles.emojiBtn}
                      onClick={() => { onReact?.(msg.id, e); setPickerOpen(false); }}
                    >
                      {e}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {isOwn && onEdit && (
            <button
              className={styles.actionBtn}
              title="Edit"
              onClick={() => setEditing(true)}
            >
              <PencilIcon />
            </button>
          )}
          {isOwn && onDelete && (
            <button
              className={`${styles.actionBtn} ${styles.deleteBtn}`}
              title="Delete"
              onClick={() => onDelete?.(msg.id)}
            >
              <TrashIcon />
            </button>
          )}
        </div>
      )}
    </article>
  );
}
