"use client";
import { useState } from "react";

export default function ChatBox() {
  const [message, setMessage] = useState("");
  const [chat, setChat] = useState([]);

  const sendMessage = () => {
    if (!message) return;
    setChat([...chat, { text: message }]);
    setMessage("");
  };

  return (
    <div className="flex flex-col h-screen relative">
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 pb-40">
        {chat.length === 0 && (
          <h1 className="text-3xl text-center text-gray-400 mt-20">
            Welcome to SARS
          </h1>
        )}

        {chat.map((msg, i) => (
          <div key={i} className="mb-3">
            <div className="bg-[#444654] p-3 rounded-lg max-w-xl">
              {msg.text}
            </div>
          </div>
        ))}
      </div>

      {/* Fixed Input */}
      <div className="absolute bottom-4 left-0 w-full px-4">
  <div className="max-w-3xl mx-auto flex items-center bg-[#40414f] rounded-xl px-4 py-3 shadow-lg">
          <input
            className="flex-1 bg-transparent outline-none text-white"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Send a message..."
          />
          <button
            onClick={sendMessage}
            className="ml-2 bg-green-500 px-4 py-1 rounded hover:bg-green-600 transition"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}