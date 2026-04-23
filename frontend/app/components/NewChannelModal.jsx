"use client";

import { useState } from "react";
import { createChannel } from "@/lib/api";
import styles from "./Modal.module.css";

export default function NewChannelModal({ courseId, token, onCreated, onClose }) {
  const [name,    setName]    = useState("");
  const [error,   setError]   = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const ch = await createChannel(courseId, name, token);
      onCreated(ch);
    } catch (err) {
      setError(err.message ?? "Failed to create channel");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>New Channel</h2>
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <form className={styles.form} onSubmit={handleSubmit}>
          <label className={styles.fieldLabel}>Channel name</label>
          <input
            className={styles.searchInput}
            placeholder="e.g. study-group"
            value={name}
            onChange={e => setName(e.target.value.toLowerCase().replace(/\s+/g, "-"))}
            autoFocus
            disabled={loading}
          />
          {error && <p className={styles.errorText}>{error}</p>}
          <button
            className={styles.submitBtn}
            type="submit"
            disabled={!name.trim() || loading}
          >
            {loading ? "Creating…" : "Create channel"}
          </button>
        </form>
      </div>
    </div>
  );
}
