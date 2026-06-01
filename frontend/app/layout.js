import Sidebar from "./components/Sidebar";
import { PomodoroProvider } from "./components/PomodoroProvider";
import "./globals.css";

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600;700&family=Inter:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200"
          rel="stylesheet"
        />
      </head>
      <body className="flex h-screen overflow-hidden bg-background text-on-surface font-sans">
        <PomodoroProvider>
          <Sidebar />
          <main className="flex-1 min-h-0 overflow-hidden flex flex-col">{children}</main>
        </PomodoroProvider>
      </body>
    </html>
  );
}