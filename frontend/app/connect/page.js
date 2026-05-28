import { Suspense } from "react";
import Connect from "./Connect";

export default function Page() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-on-surface-variant">Loading…</p>
        </div>
      </div>
    }>
      <Connect />
    </Suspense>
  );
}