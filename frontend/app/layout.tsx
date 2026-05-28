import Sidebar from "./components/Sidebar";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden bg-[#343541] text-white">
        <Sidebar />
        <main className="flex-1 h-screen overflow-y-auto flex flex-col">
          {children}
        </main>
      </body>
    </html>
  );
}