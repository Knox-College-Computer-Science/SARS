"use client";

import { useState, useEffect, useCallback } from "react";
import ChatSidebar from "../components/ChatSidebar";
import ChatArea from "../components/ChatArea";
import DMArea from "../components/DMArea";
import {
  schoolLaunch,
  fetchWorkspace,
  fetchConversations,
  getOrCreateConversation,
} from "@/lib/api";
import socket from "@/lib/socket";
import styles from "./page.module.css";

const COURSE_ID = "CHEM101";

export default function ForumPage() {
  const [currentUser,   setCurrentUser]   = useState(null);
  const [token,         setToken]         = useState(null);
  const [course,        setCourse]        = useState(null);
  const [channels,      setChannels]      = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeView,    setActiveView]    = useState(null);
  const [onlineUsers,   setOnlineUsers]   = useState(new Set());
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState(null);

  useEffect(() => {
    async function init() {
      try {
        const auth = await schoolLaunch(COURSE_ID);
        const { token: t, user, course: c } = auth;

        setCurrentUser(user);
        setToken(t);

        const [wsData, convData] = await Promise.all([
          fetchWorkspace(COURSE_ID, t),
          fetchConversations(t),
        ]);

        const chs   = wsData.channels       ?? [];
        const convs = convData.conversations ?? [];

        setCourse({ ...c, ...wsData.course });
        setChannels(chs);
        setConversations(convs);

        if (chs.length > 0) {
          setActiveView({ type: "channel", channelId: chs[0].id, channelName: chs[0].name });
        }
      } catch (err) {
        console.error("Forum init error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    if (!socket.connected) socket.connect();

    socket.emit("user_auth", { user_id: currentUser.id });

    function onOnlineUsers(data) {
      setOnlineUsers(new Set(data.users));
    }
    socket.on("online_users", onOnlineUsers);
    return () => socket.off("online_users", onOnlineUsers);
  }, [currentUser]);

  const handleSelectChannel = useCallback((channel) => {
    setActiveView({ type: "channel", channelId: channel.id, channelName: channel.name });
  }, []);

  const handleSelectDM = useCallback((conv) => {
    setActiveView({
      type:           "dm",
      conversationId: conv.id,
      recipient:      conv.recipient,
    });
  }, []);

  const handleStartDM = useCallback(async (member) => {
    if (!currentUser) return;
    try {
      const data = await getOrCreateConversation(currentUser.id, member.id);
      const newConv = {
        id:        data.conversation_id,
        recipient: { id: member.id, name: member.name, initials: member.initials },
        last_message: null,
      };
      setConversations(prev => {
        if (prev.find(c => c.id === newConv.id)) return prev;
        return [newConv, ...prev];
      });
      setActiveView({
        type:           "dm",
        conversationId: newConv.id,
        recipient:      newConv.recipient,
      });
    } catch (err) {
      console.error("Start DM failed:", err);
    }
  }, [currentUser]);

  const handleChannelCreated = useCallback((channel) => {
    setChannels(prev => [...prev, channel]);
  }, []);

  if (loading) {
    return (
      <div className={styles.splash}>
        <div className={styles.splashLogo}>Discussion</div>
        <div className={styles.splashSub}>Connecting…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.splash}>
        <div className={styles.splashLogo}>Discussion</div>
        <div className={styles.splashError}>
          Could not connect to backend.
          <br />
          <small>Make sure the API is running on port 8000.</small>
          <br />
          <button className={styles.retryBtn} onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.app}>
      <ChatSidebar
        course={course}
        channels={channels}
        conversations={conversations}
        activeView={activeView}
        onSelectChannel={handleSelectChannel}
        onSelectDM={handleSelectDM}
        onStartDM={handleStartDM}
        onChannelCreated={handleChannelCreated}
        currentUser={currentUser}
        token={token}
        courseId={COURSE_ID}
        onlineUsers={onlineUsers}
      />

      <main className={styles.main}>
        {activeView?.type === "channel" && (
          <ChatArea
            key={activeView.channelId}
            channelId={activeView.channelId}
            channelName={activeView.channelName}
            currentUser={currentUser}
            memberCount={course?.member_count ?? 0}
          />
        )}
        {activeView?.type === "dm" && (
          <DMArea
            key={activeView.conversationId}
            conversationId={activeView.conversationId}
            recipient={activeView.recipient}
            currentUser={currentUser}
          />
        )}
        {!activeView && (
          <div className={styles.welcome}>
            <div className={styles.welcomeIcon}>💬</div>
            <h2>Welcome to {course?.name ?? "Discussion"}</h2>
            <p>Pick a channel or direct message to get started.</p>
          </div>
        )}
      </main>
    </div>
  );
}
