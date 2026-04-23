"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function Connect() {
  const searchParams = useSearchParams();
  const [googleConnected, setGoogleConnected] = useState(false);

  useEffect(() => {
    const connected = searchParams.get("connected");

    if (connected === "true") {
      setGoogleConnected(true);
    }
  }, [searchParams]);

  const handleGoogleConnect = () => {
  window.location.href = "http://localhost:8000/auth/google/login";
  };


  return (
    <div className="p-8 text-white max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">🔗 Connect Your Accounts</h1>
      <p className="text-gray-400 mb-8 text-sm">
        Connect to Google Classroom or Brightspace to sync your courses and assignments.
      </p>

      {/* Google Classroom Card */}
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

          {/* Status badge */}
          <span
            className={`text-xs px-3 py-1 rounded-full font-medium ${
              googleConnected
                ? "bg-green-500 text-white"
                : "bg-gray-600 text-gray-300"
            }`}
          >
            {googleConnected ? "✅ Connected" : "Not connected"}
          </span>
        </div>

        {!googleConnected ? (
          <button
            onClick={handleGoogleConnect}
            className="w-full bg-blue-500 hover:bg-blue-600 transition p-2 rounded-lg font-medium"
          >
            Connect with Google
          </button>
        ) : (
          <div className="bg-[#343541] rounded-lg p-3 text-sm text-gray-300">
             Google Classroom is connected. Your courses will sync automatically.
            <button
              onClick={() => setGoogleConnected(false)}
              className="ml-4 text-red-400 hover:text-red-300 text-xs underline"
            >
              Disconnect
            </button>
          </div>
        )}
      </div>

      
      {/* Info note */}
      <p className="text-gray-500 text-xs mt-6 text-center">
        ⚠️ Real OAuth integration will be added in the next phase. This UI is ready to plug in.
      </p>
    </div>
  );
}