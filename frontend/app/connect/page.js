import { Suspense } from "react";
import Connect from "./Connect";

export default function Page() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <Connect />
    </Suspense>
  );
}