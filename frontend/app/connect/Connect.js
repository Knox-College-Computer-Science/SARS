"use client";
import { useEffect, useState } from "react";

export default function Connect() {
  const [googleConnected,    setGoogleConnected   ] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(true);

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

  async function checkGoogleConnection() {
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
      if (err.name !== "AbortError") console.error(err);
      setGoogleConnected(false);
    } finally {
      clearTimeout(timeout);
      setCheckingConnection(false);
    }
  }

  function handleGoogleConnect() {
    window.location.href = "/api/auth/google/login";
  }

  async function handleGoogleDisconnect() {
    try {
      const res = await fetch("/api/auth/google/disconnect", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Failed to disconnect");
      setGoogleConnected(false);
    } catch (err) {
      console.error(err);
      alert("Failed to disconnect Google Classroom.");
    }
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center p-8">

      {/* Page header */}
      <div className="max-w-2xl w-full text-center mb-10 mt-8">
        <div className="inline-flex items-center gap-2 bg-primary/10 px-4 py-2 rounded-full text-primary border border-primary/30 mb-4">
          <span className="material-symbols-outlined" style={{ fontSize: 16, fontVariationSettings: '"FILL" 1' }}>link</span>
          <span className="text-xs font-bold uppercase tracking-widest">Connect Your Accounts</span>
        </div>
        <h2 className="font-display text-4xl font-bold text-on-surface tracking-tight mb-3">
          Sync Your Academic Workspace
        </h2>
        <p className="text-sm text-on-surface-variant leading-relaxed max-w-xl mx-auto">
          Connect to Google Classroom to automatically sync your courses,
          upcoming assignments, and lecture notes directly to your SARS dashboard.
        </p>
      </div>

      {/* Main card */}
      <div className="max-w-xl w-full">
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-8 shadow-2xl relative overflow-hidden">
          {/* Subtle glow */}
          <div className="absolute -top-24 -right-24 w-48 h-48 rounded-full pointer-events-none"
            style={{ background: "rgba(180,197,255,0.08)", filter: "blur(60px)" }} />

          {/* Card header */}
          <div className="flex items-start justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-white rounded-xl flex items-center justify-center shadow-inner flex-shrink-0">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: 32, fontVariationSettings: '"FILL" 1' }}>
                  school
                </span>
              </div>
              <div>
                <h3 className="text-xl font-semibold text-on-surface">Google Classroom</h3>
                <p className="text-sm text-on-surface-variant">Sync courses, assignments, and grades.</p>
              </div>
            </div>

            {/* Status badge */}
            {checkingConnection ? (
              <div className="flex items-center gap-2 px-3 py-1 bg-surface-container-highest border border-outline-variant rounded-full">
                <div className="w-2 h-2 rounded-full bg-outline animate-pulse" />
                <span className="text-[10px] font-bold uppercase text-on-surface-variant">Checking…</span>
              </div>
            ) : googleConnected ? (
              <div className="flex items-center gap-2 px-3 py-1 rounded-full"
                style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)" }}>
                <span className="material-symbols-outlined" style={{ fontSize: 16, color: "#22c55e", fontVariationSettings: '"FILL" 1' }}>check_circle</span>
                <span className="text-[10px] font-bold uppercase" style={{ color: "#22c55e" }}>Connected</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-3 py-1 bg-surface-container-highest border border-outline-variant rounded-full">
                <div className="w-2 h-2 rounded-full bg-outline animate-pulse" />
                <span className="text-[10px] font-bold uppercase text-on-surface-variant">Not connected</span>
              </div>
            )}
          </div>

          {/* Feature list */}
          <div className="space-y-3 mb-8">
            {[
              "Automatic calendar syncing for deadlines",
              "Import lecture materials to your AI Assistant",
            ].map((feature) => (
              <div key={feature} className="flex items-center gap-3 text-on-surface-variant">
                <span className="material-symbols-outlined text-primary" style={{ fontSize: 18 }}>check_circle</span>
                <span className="text-sm">{feature}</span>
              </div>
            ))}
          </div>

          {/* Action area */}
          {!checkingConnection && !googleConnected && (
            <button
              onClick={handleGoogleConnect}
              className="group w-full bg-primary-container text-on-primary font-semibold py-3 rounded-lg flex items-center justify-center gap-3 hover:brightness-110 active:scale-[0.98] transition-all"
              style={{ boxShadow: "0 4px 24px rgba(98,138,255,0.25)" }}
            >
              <span>Connect with Google</span>
              <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform" style={{ fontSize: 20 }}>
                arrow_forward
              </span>
            </button>
          )}

          {!checkingConnection && googleConnected && (
            <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
              </div>
              <div className="h-px bg-outline-variant/30 mb-3" />
              <div className="flex items-center justify-between">
                <p className="text-xs text-on-surface-variant">
                  Google Classroom is connected. Your courses will sync automatically.
                </p>
                <button
                  onClick={handleGoogleDisconnect}
                  className="text-xs text-error font-bold hover:underline ml-4 flex-shrink-0"
                >
                  Disconnect
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer note */}
        <div className="mt-4 flex items-start gap-3 px-2 text-on-surface-variant opacity-60">
          <span className="material-symbols-outlined flex-shrink-0" style={{ fontSize: 16 }}>info</span>
          <p className="text-xs leading-relaxed">
            Google Classroom OAuth is active. Your data is encrypted and only synced from the
            current term. You can revoke access at any time from your Google Account settings.
          </p>
        </div>

        {/* Coming soon */}
        <div className="mt-4 border border-dashed border-outline-variant rounded-xl p-5 flex items-center justify-center gap-3 opacity-50 cursor-not-allowed">
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 20 }}>grid_view</span>
          <span className="text-xs font-bold text-on-surface-variant">Add Brightspace Integration (Coming Soon)</span>
        </div>
      </div>

    </div>
  );
}