"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/",        label: "Home",        icon: "home"        },
  { href: "/upload",  label: "Upload",      icon: "upload_file" },
  { href: "/notes",   label: "Notes",       icon: "description" },
  { href: "/forum",   label: "Discussion",  icon: "forum"       },
  { href: "/ai",      label: "AI Assistant",icon: "smart_toy"   },
  { href: "/connect", label: "Connect",     icon: "link"        },
];

export default function Sidebar() {
  const [open, setOpen] = useState(true);
  const pathname = usePathname();

  return (
    <aside
      className={`${
        open ? "w-60" : "w-16"
      } flex-shrink-0 h-screen bg-surface-container-low border-r border-outline-variant flex flex-col transition-all duration-300 ease-in-out overflow-hidden`}
    >
      {/* Brand + Toggle */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-outline-variant">
        {open && (
          <div>
            <h1 className="font-display text-xl font-bold text-on-surface leading-none">
              SARS
            </h1>
            <p className="text-[11px] text-on-surface-variant opacity-70 mt-0.5">
              Academic Hub
            </p>
          </div>
        )}
        <button
          onClick={() => setOpen(!open)}
          aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
          className={`text-on-surface-variant hover:text-primary transition-colors ${!open ? "mx-auto" : ""}`}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 22 }}>
            {open ? "menu_open" : "menu"}
          </span>
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex flex-col gap-0.5 p-2 flex-1">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-150 group ${
                isActive
                  ? "bg-surface-container-highest text-on-surface border border-outline-variant"
                  : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
              }`}
            >
              <span
                className="material-symbols-outlined flex-shrink-0"
                style={{
                  fontSize: 20,
                  fontVariationSettings: isActive ? '"FILL" 1' : '"FILL" 0',
                }}
              >
                {icon}
              </span>
              {open && (
                <span className="text-sm font-medium whitespace-nowrap">
                  {label}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}