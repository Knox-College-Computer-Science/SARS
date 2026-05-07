"use client";
import { useState } from "react";
import Link from "next/link";

export default function Sidebar() {
  const [open, setOpen] = useState(true);

  return (
    <div
      className={`${
        open ? "w-64" : "w-16"
      } bg-[#202123] h-screen p-3 transition-all duration-300 ease-in-out`}
    >
      {/* Toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="text-gray-300 mb-6 hover:text-white transition"
      >
        ☰
      </button>

      {/* Menu */}
      <div className="text-white">
        <SidebarItem href="/" label="Home" icon="🏠" open={open} />
        <SidebarItem href="/upload" label="Upload" icon="📤" open={open} />
        <SidebarItem href="/notes" label="Notes" icon="📂" open={open} />
        <SidebarItem href="/forum" label="Discussion" icon="💬" open={open} />
        <SidebarItem href="/ai" label="AI Assistant" icon="🤖" open={open} />
        <SidebarItem href="/connect" label="Connect" icon="🔗" open={open} />
      </div>
    </div>
  );
}

function SidebarItem({ href, label, icon, open }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 p-2 rounded hover:bg-gray-700 transition-all duration-200"
    >
      <span>{icon}</span>
      <span
        className={`transition-all duration-200 ${
          open ? "opacity-100" : "opacity-0 hidden"
        }`}
      >
        {label}
      </span>
    </Link>
  );
}