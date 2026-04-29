"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Message from "./Message";
import styles from "./ChatArea.module.css";
import socket from "@/lib/socket";
import {
  fetchChannelMessages,
  postChannelMessage,
  editChannelMessage,
  deleteChannelMessage,
  reactToMessage,
  normaliseMessage,
} from "@/lib/api";

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function DateSeparator({ label }) {
  return (
    <div className={styles.dateSep}>
      <span className={styles.dateLine} />
      <span className={styles.dateLabel}>{label}</span>
      <span className={styles.dateLine} />
    </div>
  );
}

function formatDateLabel(isoString) {
  if (!isoString) return null;
  const d = new Date(isoString);
  if (isNaN(d)) return null;
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  return d.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
}

function buildFeed(messages) {
  const items = [];
  let lastDateLabel = null;
  let lastSenderId = null;

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    const label = formatDateLabel(msg.sentAt);

    if (label && label !== lastDateLabel) {
      items.push({ type: "date", label, key: `date-${label}` });
      lastDateLabel = label;
      lastSenderId = null;
    }

    const compact = msg.senderId === lastSenderId;
    items.push({ type: "msg", msg, compact });
    lastSenderId = msg.senderId;
  }
  return items;
}

export default function ChatArea({ channelId, channelName, currentUser, memberCount }) {
  const [messages,   setMessages]   = useState([]);
  const [input,      setInput]      = useState("");
  const [sending,    setSending]    = useState(false);
  const [typingUser, setTypingUser] = useState(null);
  const [connected,  setConnected]  = useState(false);
  const bottomRef  = useRef(null);
  const inputRef   = useRef(null);
  const typingRef  = useRef(null);

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

    fetchChannelMessages(channelId)
      .then(data => setMessages(data.messages))
      .catch(console.error);

    socket.emit("join_channel", { channel_id: channelId });
    return () => socket.emit("leave_channel", { channel_id: channelId });
  }, [channelId]);

  useEffect(() => {
    function onNew(raw) {
      const msg = normaliseMessage(raw);
      setMessages(prev => prev.find(m => m.id === msg.id) ? prev : [...prev, msg]);
    }
    function onEdited(raw) {
      const msg = normaliseMessage(raw);
      setMessages(prev => prev.map(m => m.id === msg.id ? msg : m));
    }
    function onDeleted({ message_id }) {
      setMessages(prev => prev.filter(m => m.id !== message_id));
    }
    function onReacted(raw) {
      const msg = normaliseMessage(raw);
      setMessages(prev => prev.map(m => m.id === msg.id ? msg : m));
    }
    function onTyping(data) {
      if (data.channel_id !== channelId) return;
      setTypingUser(data.name);
      clearTimeout(typingRef.current);
      typingRef.current = setTimeout(() => setTypingUser(null), 3000);
    }
    function onStopTyping(data) {
      if (data.channel_id !== channelId) return;
      setTypingUser(null);
    }

    socket.on("new_channel_message", onNew);
    socket.on("message_edited",      onEdited);
    socket.on("message_deleted",     onDeleted);
    socket.on("message_reacted",     onReacted);
    socket.on("user_typing",         onTyping);
    socket.on("user_stopped_typing", onStopTyping);

    return () => {
      socket.off("new_channel_message", onNew);
      socket.off("message_edited",      onEdited);
      socket.off("message_deleted",     onDeleted);
      socket.off("message_reacted",     onReacted);
      socket.off("user_typing",         onTyping);
      socket.off("user_stopped_typing", onStopTyping);
    };
  }, [channelId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingUser]);

  const handleInput = useCallback((e) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 130) + "px";
    socket.emit("typing_start", { channel_id: channelId, name: currentUser.name });
  }, [channelId, currentUser?.name]);

  const handleKey = useCallback((e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }, [input]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    const tempId = `temp-${Date.now()}`;
    const optimistic = {
      id:             tempId,
      channelId,
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
    socket.emit("typing_stop", { channel_id: channelId });

    setSending(true);
    try {
      const saved = await postChannelMessage(channelId, text, currentUser.id);
      setMessages(prev => prev.map(m => m.id === tempId ? saved : m));
    } catch (err) {
      console.error("Send failed:", err);
      setMessages(prev => prev.map(m => m.id === tempId ? { ...m, failed: true } : m));
    } finally {
      setSending(false);
    }
  }

  async function handleEdit(messageId, newContent) {
    try {
      const saved = await editChannelMessage(channelId, messageId, newContent, currentUser.id);
      setMessages(prev => prev.map(m => m.id === messageId ? saved : m));
    } catch (err) {
      console.error("Edit failed:", err);
    }
  }

  async function handleDelete(messageId) {
    setMessages(prev => prev.filter(m => m.id !== messageId));
    try {
      await deleteChannelMessage(channelId, messageId, currentUser.id);
    } catch (err) {
      console.error("Delete failed:", err);
    }
  }

  async function handleReact(messageId, emoji) {
    try {
      const updated = await reactToMessage(channelId, messageId, currentUser.id, emoji);
      setMessages(prev => prev.map(m => m.id === messageId ? updated : m));
    } catch (err) {
      console.error("React failed:", err);
    }
  }

  const isAnnouncements = channelName === "announcements";
  const feed = buildFeed(messages);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.hash}>#</span>
          <span className={styles.channelName}>{channelName}</span>
          <span className={styles.memberCount}>· {memberCount} members</span>
        </div>
        {connected && <span className={styles.livePill}>● live</span>}
      </div>

      <div className={styles.feed}>
        {messages.length === 0 && (
          <p className={styles.emptyHint}>No messages yet — start the conversation!</p>
        )}

        {feed.map(item =>
          item.type === "date" ? (
            <DateSeparator key={item.key} label={item.label} />
          ) : (
            <Message
              key={item.msg.id}
              msg={item.msg}
              isOwn={item.msg.senderId === currentUser?.id}
              currentUser={currentUser}
              compact={item.compact}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onReact={handleReact}
            />
          )
        )}

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

      {isAnnouncements ? (
        <div className={styles.announcementBanner}>
          Only teachers can post in #announcements
        </div>
      ) : (
        <div className={styles.composer}>
          <textarea
            ref={inputRef}
            className={styles.inputBox}
            placeholder={`Message #${channelName}`}
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
      )}
    </div>
  );
}
