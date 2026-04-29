"use client";

import { useState, useEffect } from "react";
import { fetchMembers } from "@/lib/api";
import styles from "./Modal.module.css";

const AVATAR_COLORS = [
  { bg: "#dff2e8", text: "#457b64" },
  { bg: "#efe1c7", text: "#8d6338" },
  { bg: "#e1e0fb", text: "#5d5bac" },
  { bg: "#d6e7f7", text: "#4771a8" },
];
function getAvatarColor(id = "") {
  const n = Array.from(id).reduce((s, c) => s + c.charCodeAt(0), 0);
  return AVATAR_COLORS[n % AVATAR_COLORS.length];
}

export default function UserPickerModal({ courseId, token, currentUser, onSelect, onClose }) {
  const [members, setMembers] = useState([]);
  const [query,   setQuery]   = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMembers(courseId, token)
      .then(data => setMembers(data.members ?? []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [courseId, token]);

  const filtered = members.filter(m =>
    m.name.toLowerCase().includes(query.toLowerCase()) ||
    m.email.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>New Direct Message</h2>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <div className={styles.searchWrap}>
          <input
            className={styles.searchInput}
            placeholder="Search by name or email…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
        </div>

        <div className={styles.list}>
          {loading && <p className={styles.hint}>Loading members…</p>}
          {!loading && filtered.length === 0 && (
            <p className={styles.hint}>No members found.</p>
          )}
          {filtered.map(member => {
            const color = getAvatarColor(member.id);
            return (
              <button
                key={member.id}
                className={styles.memberItem}
                onClick={() => onSelect(member)}
              >
                <div
                  className={styles.memberAvatar}
                  style={{ backgroundColor: color.bg, color: color.text }}
                >
                  {member.initials}
                </div>
                <div className={styles.memberInfo}>
                  <span className={styles.memberName}>{member.name}</span>
                  <span className={styles.memberRole}>{member.role}</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
