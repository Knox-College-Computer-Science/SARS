"use client";

export default function ConnectGoogleClassroomCard({
  message = "Connect Google Classroom to continue using this feature.",
  title = "Connect Google Classroom",
}) {
  return (
    <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-outline-variant bg-surface-container p-7 shadow-2xl">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "radial-gradient(circle, #b4c5ff 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />

      <div className="relative z-10 flex items-start gap-5">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary-container">
          <span
            className="material-symbols-outlined text-on-primary"
            style={{ fontSize: 30 }}
          >
            school
          </span>
        </div>

        <div className="flex-1">

          <h2 className="font-display text-2xl font-bold text-on-surface">
            {title}
          </h2>

          <p className="mt-3 max-w-xl text-sm leading-relaxed text-on-surface-variant">
            {message}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <a
              href="/connect"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-on-primary transition hover:brightness-110 active:scale-95"
            >
              Go to Connect Page
              <span
                className="material-symbols-outlined"
                style={{ fontSize: 17 }}
              >
                arrow_forward
              </span>
            </a>

            <span className="text-xs text-on-surface-variant">
              This lets SARS access your current classes, assignments, and materials.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}