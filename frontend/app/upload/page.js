"use client";

import { useEffect, useState } from "react";
import UploadBox from "../components/UploadBox";
import ConnectGoogleClassroomCard from "../components/ConnectGoogleClassroomCard";

export default function UploadPage() {
  const [isConnected, setIsConnected] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(true);

  useEffect(() => {
    checkGoogleConnection();
  }, []);

  const checkGoogleConnection = async () => {
    setCheckingConnection(true);

    try {
      const res = await fetch("/api/auth/google/me", {
        credentials: "include",
      });

      if (!res.ok) {
        setIsConnected(false);
        return;
      }

      const data = await res.json();

      if (data.user && data.has_access_token) {
        setIsConnected(true);
      } else {
        setIsConnected(false);
      }
    } catch (err) {
      console.error("Failed to check Google connection:", err);
      setIsConnected(false);
    } finally {
      setCheckingConnection(false);
    }
  };

  if (checkingConnection) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-8 text-white">
        <div className="w-full max-w-2xl min-h-[220px] bg-[#444654] rounded-xl p-8 shadow-lg flex items-center justify-center">
          <p className="text-gray-300">Checking Google Classroom connection...</p>
        </div>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="p-6 text-white">
        <h1 className="text-4xl font-bold text-center mb-10">
          📤 Upload Notes
        </h1>

        <div className="min-h-[60vh] flex items-center justify-center">
          <ConnectGoogleClassroomCard
            message="Connect Google Classroom before uploading notes so your notes can be linked to your current classes."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 text-white">
      <h1 className="text-2xl font-semibold mb-4">📤 Upload Notes</h1>
      <UploadBox />
    </div>
  );
}