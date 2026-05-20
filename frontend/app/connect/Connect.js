"use client";
import { useEffect, useState } from "react";

export default function Connect() {
  const [googleConnected, setGoogleConnected] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(true);

  const handleGoogleConnect = () => {
    window.location.href = "/api/auth/google/login"; 
  };

  const handleGoogleDisconnect = async () => {
    try {
      const res = await fetch("/api/auth/google/disconnect", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to disconnect");
      setGoogleConnected(false);
    } catch (err) {
      console.error("Failed to disconnect:", err);
      alert("Failed to disconnect Google Classroom.");
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionToken = params.get("session_token");
    if (sessionToken) {
      fetch(`/api/auth/session/restore?token=${sessionToken}`, { credentials: "include" })
        .finally(() => {
          window.history.replaceState({}, "", "/connect");
          checkGoogleConnection();
        });
    } else {
      checkGoogleConnection();
    }
  }, []);

  const checkGoogleConnection = async () => {
    setCheckingConnection(true);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch("/api/auth/google/me", { 
        credentials: "include",
        signal: controller.signal,
      });
      if (res.ok) {
        const data = await res.json();
        setGoogleConnected(Boolean(data.user && data.has_access_token));
      } else {
        setGoogleConnected(false);
      }
    } catch (err) {
      if (err.name !== "AbortError") console.error("Connection check failed:", err);
      setGoogleConnected(false);
    } finally {
      clearTimeout(timeout);
      setCheckingConnection(false);
    }
  };

  return (
    <div className="p-8 text-white max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">🔗 Connect Your Accounts</h1>
      <p className="text-gray-400 mb-8 text-sm">
        Connect to Google Classroom or Brightspace to sync your courses and assignments.
      </p>

      <div className="bg-[#444654] rounded-xl p-6 mb-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="bg-white rounded-full p-2 w-10 h-10 flex items-center justify-center text-xl">
              🎓
            </div>
            <div>
              <h2 className="font-semibold text-lg">Google Classroom</h2>
              <p className="text-gray-400 text-sm">Sync courses and assignments</p>
            </div>
          </div>
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${
            googleConnected ? "bg-green-500 text-white" : "bg-gray-600 text-gray-300"
          }`}>
            {checkingConnection ? "Checking..." : googleConnected ? "✅ Connected" : "Not connected"}
          </span>
        </div>

        {!checkingConnection && !googleConnected ? (
          <button
            onClick={handleGoogleConnect}
            className="w-full bg-blue-500 hover:bg-blue-600 transition p-2 rounded-lg font-medium"
          >
            Connect with Google
          </button>
        ) : !checkingConnection && googleConnected ? (
          <div className="bg-[#343541] rounded-lg p-3 text-sm text-gray-300">
            Google Classroom is connected. Your courses will sync automatically.
            <button
              onClick={handleGoogleDisconnect}
              className="ml-4 text-red-400 hover:text-red-300 text-xs underline"
            >
              Disconnect
            </button>
          </div>
        ) : null}
      </div>

      <p className="text-gray-500 text-xs mt-6 text-center">
        Google Classroom OAuth is active. Connected courses are synced from your current term.
      </p>
    </div>
  );
}