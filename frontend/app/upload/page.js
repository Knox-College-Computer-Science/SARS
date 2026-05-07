"use client";

import { useEffect, useState } from "react";
import UploadBox from "../components/UploadBox";

export default function UploadPage() {
  const [isConnected, setIsConnected] = useState(false);
  const [checkingConnection, setCheckingConnection] = useState(true);

  useEffect(() => {
    checkGoogleConnection();
  }, []);

  const checkGoogleConnection = async () => {
    setCheckingConnection(true);

    try {
      const res = await fetch("http://localhost:8000/auth/google/me", {
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

  const goToConnectPage = () => {
    window.location.href = "/connect";
  };

  if (checkingConnection) {
    return (
      <div className="p-6 text-white">
        <p className="text-gray-400">Checking Google Classroom connection...</p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="p-6 text-white">
        <h1 className="text-2xl font-semibold mb-4">📤 Upload Notes</h1>

        <div className="bg-[#2f3342] border border-gray-600 rounded-lg p-6 max-w-xl">
          <h2 className="text-xl font-semibold mb-2">
            Connect Google Classroom
          </h2>

          <p className="text-gray-300 mb-4">
            Connect to Google Classroom before uploading notes so your notes can
            be linked to your current classes.
          </p>

          <button
            onClick={goToConnectPage}
            className="bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg text-sm font-medium"
          >
            Go to Connect Page
          </button>
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