"use client";

import { useState, useEffect, useCallback } from "react";
import ChatSidebar from "../components/ChatSidebar";
import ChatArea from "../components/ChatArea";
import DMArea from "../components/DMArea";
import ConnectGoogleClassroomCard from "../components/ConnectGoogleClassroomCard";
import {
  syncClassroomCourses,
  fetchWorkspace,
  fetchConversations,
  getOrCreateConversation,
} from "@/lib/api";
import socket from "@/lib/socket";
import styles from "./page.module.css";

export default function ForumPage() {
  const [currentUser,   setCurrentUser]   = useState(null);
  const [token,         setToken]         = useState(null);
  const [course,        setCourse]        = useState(null);
  const [courses,       setCourses]       = useState([]);
  const [channels,      setChannels]      = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeView,    setActiveView]    = useState(null);
  const [onlineUsers,      setOnlineUsers]      = useState(new Set());
  const [userStatuses,     setUserStatuses]     = useState({});
  const [loading,          setLoading]          = useState(true);
  const [error,            setError]            = useState(null);
  const [isGoogleConnected, setIsGoogleConnected] = useState(true);
  const [noCourses, setNoCourses] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        let t, user, allCourses;

        let googleConnected = false;

        try {
          const meRes = await fetch("/api/auth/google/me", { credentials: "include" });
          googleConnected = meRes.ok;
        } catch {}

        if (googleConnected) {
          const syncData = await syncClassroomCourses();
          t = syncData.token;
          user = syncData.user;
          allCourses = [...(syncData.courses ?? [])].sort(
            (a, b) => (b.is_current_term ? 1 : 0) - (a.is_current_term ? 1 : 0)
          );
        } else {
          setIsGoogleConnected(false);
          setLoading(false);
          return;
        }

        setCurrentUser(user);
        setToken(t);
        setCourses(allCourses);

        if (allCourses.length === 0) {
          setCurrentUser(user);
          setToken(t);
          setCourses([]);
          setChannels([]);
          setConversations([]);
          setCourse(null);
          setActiveView(null);
          setNoCourses(true);
          return;
        }

        const initialCourseId = allCourses[0].school_course_id;

        const [wsData, convData] = await Promise.all([
          fetchWorkspace(initialCourseId, t),
          fetchConversations(t),
        ]);

        const chs   = wsData.channels       ?? [];
        const convs = convData.conversations ?? [];

        setCourse({ ...(allCourses[0] ?? {}), ...wsData.course });
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
    function onUserStatuses(data) {
      setUserStatuses(data.statuses ?? {});
    }
    socket.on("online_users",   onOnlineUsers);
    socket.on("user_statuses",  onUserStatuses);
    return () => {
      socket.off("online_users",  onOnlineUsers);
      socket.off("user_statuses", onUserStatuses);
    };
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

  const handleSelectCourse = useCallback(async (selectedCourse) => {
    if (!token || !selectedCourse) return;
    try {
      const wsData = await fetchWorkspace(selectedCourse.school_course_id, token);
      const chs = wsData.channels ?? [];
      setCourse({ ...selectedCourse, ...wsData.course });
      setChannels(chs);
      if (chs.length > 0) {
        setActiveView({ type: "channel", channelId: chs[0].id, channelName: chs[0].name });
      } else {
        setActiveView(null);
      }
    } catch (err) {
      console.error("Course switch failed:", err);
    }
  }, [token]);

  if (!isGoogleConnected) {
    return (
      <div className={styles.app}>
        <main className={`${styles.main} ${styles.connectMain}`}>
          <ConnectGoogleClassroomCard
            message="Connect Google Classroom to access course channels and direct messages with your classmates."
          />
        </main>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={styles.splash}>
        <div className={styles.splashLogo}>Discussion</div>
        <div className={styles.splashSub}>Connecting…</div>
      </div>
    );
  }

  if (noCourses) {
    return (
      <div className="p-6 text-white">
        <h1 className="text-3xl font-bold text-center mb-10">
          💬 Discussion
        </h1>

        <div className="min-h-[60vh] flex items-center justify-center">
          <div className="w-full max-w-2xl min-h-[220px] bg-[#444654] rounded-xl p-8 shadow-lg flex flex-col justify-center">
            <h2 className="text-2xl font-semibold mb-4">
              No current courses found
            </h2>
            <p className="text-gray-300 leading-relaxed">
              Google Classroom is connected, but no current-term courses were found for discussion channels.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.splash}>
        <div className={styles.splashLogo}>Discussion</div>
        <div className={styles.splashError}>
          {error || "Could not connect to backend."}
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
        courses={courses}
        channels={channels}
        conversations={conversations}
        activeView={activeView}
        onSelectChannel={handleSelectChannel}
        onSelectDM={handleSelectDM}
        onStartDM={handleStartDM}
        onChannelCreated={handleChannelCreated}
        onSelectCourse={handleSelectCourse}
        currentUser={currentUser}
        token={token}
        courseId={course?.school_course_id}
        onlineUsers={onlineUsers}
        userStatuses={userStatuses}
      />

      <main className={styles.main}>
        {activeView?.type === "channel" && (
          <ChatArea
            key={activeView.channelId}
            channelId={activeView.channelId}
            channelName={activeView.channelName}
            currentUser={currentUser}
            memberCount={course?.member_count ?? 0}
            readOnly={course?.is_current_term === false}
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
