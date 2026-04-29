"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Message from "./Message";
import styles from "./ChatArea.module.css";
import dmStyles from "./DMArea.module.css";
import socket from "@/lib/socket";
import { fetchDMMessages, postDM, normaliseMessage } from "@/lib/api";

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

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

export default function DMArea({ conversationId, recipient, currentUser }) {
  const [messages,    setMessages]    = useState([]);
  const [input,       setInput]       = useState("");
  const [sending,     setSending]     = useState(false);
  const [typingUser,  setTypingUser]  = useState(null);
  const [connected,   setConnected]   = useState(false);
  const bottomRef = useRef(null);
  const inputRef  = useRef(null);
  const typingRef = useRef(null);

  useEffect(() => {
    if (!socket.connected) socket.connect();
    const onConnect    = () => setConnected(true);
    const onDisconnect = () => setConnected(false);
    socket.on("connect",    onConnect);
    socket.on("disconnect", onDisconnect);
    if (socket.connected) setConnected(true);
    return () => {
      socket.off("connect",    onConnect);
      socket.off("disconnect", onDisconnect);
    };
  }, []);

  useEffect(() => {
    setMessages([]);
    setTypingUser(null);

    fetchDMMessages(conversationId)
      .then(data => setMessages(data.messages))
      .catch(console.error);

    socket.emit("join_conversation", { conversation_id: conversationId });
    return () => socket.emit("leave_conversation", { conversation_id: conversationId });
  }, [conversationId]);

  useEffect(() => {
    function onNewDM(raw) {
      if (raw.conversation_id !== conversationId) return;
      const msg = normaliseMessage(raw);
      setMessages(prev => prev.find(m => m.id === msg.id) ? prev : [...prev, msg]);
    }
    function onTyping(data) {
      if (data.conversation_id !== conversationId) return;
      setTypingUser(data.name);
      clearTimeout(typingRef.current);
      typingRef.current = setTimeout(() => setTypingUser(null), 3000);
    }
    function onStopTyping(data) {
      if (data.conversation_id !== conversationId) return;
      setTypingUser(null);
    }

    socket.on("new_dm",                 onNewDM);
    socket.on("dm_user_typing",         onTyping);
    socket.on("dm_user_stopped_typing", onStopTyping);

    return () => {
      socket.off("new_dm",                 onNewDM);
      socket.off("dm_user_typing",         onTyping);
      socket.off("dm_user_stopped_typing", onStopTyping);
    };
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUser]);

  const handleInput = useCallback((e) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 130) + "px";
    socket.emit("dm_typing_start", { conversation_id: conversationId, name: currentUser.name });
  }, [conversationId, currentUser?.name]);

  const handleKey = useCallback((e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }, [input]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    const tempId = `temp-${Date.now()}`;
    const optimistic = {
      id:             tempId,
      conversationId,
      senderId:       currentUser.id,
      senderName:     currentUser.name,
      senderInitials: currentUser.initials,
      content:        text,
      sentAt:         new Date().toISOString(),
      reactions:      {},
    };
    setMessages(prev => [...prev, optimistic]);
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    socket.emit("dm_typing_stop", { conversation_id: conversationId });

    setSending(true);
    try {
      const saved = await postDM(conversationId, text, currentUser.id);
      setMessages(prev => prev.map(m => m.id === tempId ? saved : m));
    } catch (err) {
      console.error("DM send failed:", err);
    } finally {
      setSending(false);
    }
  }

  const color = getAvatarColor(recipient?.id ?? "");

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div
            className={dmStyles.recipientAvatar}
            style={{ backgroundColor: color.bg, color: color.text }}
          >
            {recipient?.initials ?? "??"}
          </div>
          <span className={styles.channelName}>{recipient?.name ?? "Unknown"}</span>
          <span className={styles.memberCount}>· Direct message</span>
        </div>
        {connected && <span className={styles.livePill}>● live</span>}
      </div>

      <div className={styles.feed}>
        {messages.length === 0 && (
          <p className={styles.emptyHint}>
            Start a conversation with {recipient?.name ?? "this person"}
          </p>
        )}
        {messages.map((msg, i) => {
          const prev = messages[i - 1];
          const compact = prev && prev.senderId === msg.senderId;
          return (
            <Message
              key={msg.id}
              msg={msg}
              isOwn={msg.senderId === currentUser?.id}
              currentUser={currentUser}
              compact={compact}
            />
          );
        })}

        {typingUser && (
          <div className={styles.typingRow}>
            <span className={styles.dot} />
            <span className={styles.dot} />
            <span className={styles.dot} />
            <span className={styles.typingText}>{typingUser} is typing…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className={styles.composer}>
        <textarea
          ref={inputRef}
          className={styles.inputBox}
          placeholder={`Message ${recipient?.name ?? ""}…`}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKey}
          rows={1}
          disabled={sending}
        />
        <button
          className={styles.sendBtn}
          onClick={send}
          disabled={!input.trim() || sending}
          title="Send (Enter)"
        >
          <SendIcon />
        </button>
      </div>
    </div>
  );
}
