"use client";

import { useEffect, useState } from "react";
import UploadBox from "../components/UploadBox";
import ConnectGoogleClassroomCard from "../components/ConnectGoogleClassroomCard";

export default function UploadPage() {
  const [isConnected,       setIsConnected      ] = useState(false);
  const [checkingConnection,setCheckingConnection] = useState(true);

  useEffect(() => { checkGoogleConnection(); }, []);

  async function checkGoogleConnection() {
    setCheckingConnection(true);
    try {
      const res  = await fetch("/api/auth/google/me", { credentials: "include" });
      if (!res.ok) { setIsConnected(false); return; }
      const data = await res.json();
      setIsConnected(!!(data.user && data.has_access_token));
    } catch (err) {
      console.error(err);
      setIsConnected(false);
    } finally {
      setCheckingConnection(false);
    }
  }

  // 1. Checking
  if (checkingConnection) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-on-surface-variant">Checking connection…</p>
        </div>
      </div>
    );
  }

  // 2. Not connected
  if (!isConnected) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center px-8 gap-6">
        <div className="text-center">
          <h1 className="font-display text-4xl font-bold text-on-surface tracking-tight">
            Upload Notes
          </h1>
        </div>
        <ConnectGoogleClassroomCard message="Connect Google Classroom before uploading notes so your notes can be linked to your current classes." />
      </div>
    );
  }

  // 3. Connected
  return <UploadBox />;
}