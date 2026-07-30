import Link from "next/link";

import type { ParticipantSession } from "@/lib/participant-session";

export function ExperimentShell({
  session,
  title,
  children,
  onClearSession,
}: {
  session: ParticipantSession | null;
  title: string;
  children: React.ReactNode;
  onClearSession?: () => void;
}) {
  return (
    <main className="app-shell">
      <header className="top-bar">
        <Link href="/experiment" className="brand-link">
          ForgettingCurve
        </Link>
        <div className="participant-chip">
          <span>{session ? session.participantCode : "No participant"}</span>
          {onClearSession ? (
            <button type="button" className="link-button" onClick={onClearSession}>
              Clear session
            </button>
          ) : null}
        </div>
      </header>
      <section className="page-heading">
        <h1>{title}</h1>
      </section>
      {children}
    </main>
  );
}
