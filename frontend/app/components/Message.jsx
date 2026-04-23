"use client";

import { useState } from "react";
import styles from "./Message.module.css";

const AVATAR_COLORS = [
  { bg: "#dff2e8", text: "#457b64" },
  { bg: "#efe1c7", text: "#8d6338" },
  { bg: "#e1e0fb", text: "#5d5bac" },
  { bg: "#d6e7f7", text: "#4771a8" },
];
const OWN_AVATAR = { bg: "#8eb6ff", text: "#10233e" };
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
  const [hovered,    setHovered]    = useState(false);
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

  return (
    <article
      className={`${styles.root} ${compact ? styles.compact : ""}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setPickerOpen(false); }}
    >
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

      {hovered && !editing && (
        <div className={styles.actions}>
          <div className={styles.emojiTriggerWrap}>
            <button
              className={styles.actionBtn}
              title="React"
              onClick={() => setPickerOpen(p => !p)}
            >
              😊
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

          {isOwn && (
            <>
              <button
                className={styles.actionBtn}
                title="Edit"
                onClick={() => setEditing(true)}
              >
                ✏️
              </button>
              <button
                className={`${styles.actionBtn} ${styles.deleteBtn}`}
                title="Delete"
                onClick={() => onDelete?.(msg.id)}
              >
                🗑
              </button>
            </>
          )}
        </div>
      )}
    </article>
  );
}
