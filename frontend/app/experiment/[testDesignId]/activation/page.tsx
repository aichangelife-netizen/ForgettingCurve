"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ExperimentShell } from "@/components/experiment/ExperimentShell";
import { ProgressMeter } from "@/components/experiment/ProgressMeter";
import { ErrorPanel, LoadingPanel } from "@/components/ui/StatusPanels";
import { completeActivationReview, getActivationNext, getActivationProgress } from "@/lib/api/assignments";
import type { ActivationNext, ActivationProgress } from "@/lib/api/types";
import { clearParticipantSession, readParticipantSession, type ParticipantSession } from "@/lib/participant-session";
import { formatDuration } from "@/lib/time-format";

export default function ActivationPage() {
  const router = useRouter();
  const params = useParams<{ testDesignId: string }>();
  const testDesignId = Number(params.testDesignId);
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [progress, setProgress] = useState<ActivationProgress | null>(null);
  const [next, setNext] = useState<ActivationNext | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    setSession(readParticipantSession());
    setLoading(true);
    setMessage(null);
    try {
      const loadedProgress = await getActivationProgress(testDesignId);
      setProgress(loadedProgress);
      if (loadedProgress.status === "active") {
        setNext(null);
        return;
      }
      setNext(await getActivationNext(testDesignId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load activation review.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testDesignId]);

  async function completeCurrent() {
    if (!next || submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const result = await completeActivationReview(testDesignId, next.assignment_id);
      if (result.design_status === "active") {
        router.push(`/experiment/${testDesignId}/delayed`);
        return;
      }
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not complete activation review.");
    } finally {
      setSubmitting(false);
    }
  }

  function clearSession() {
    clearParticipantSession();
    router.push("/");
  }

  return (
    <ExperimentShell session={session} title="Activation Review" onClearSession={clearSession}>
      {loading ? <LoadingPanel message="Loading activation review..." /> : null}
      {message ? <ErrorPanel message={message} onRetry={load} /> : null}
      <section className="panel">
        <h2>Final Review</h2>
        <p>
          This is a final review, not a test. Each word receives its own memory-time anchor when you continue, and
          future delayed tests are scheduled from that timestamp.
        </p>
        {progress ? (
          <ProgressMeter
            label="Reviewed words"
            value={progress.anchored_assignment_count}
            total={progress.total_assignment_count}
          />
        ) : null}
      </section>
      {progress?.status === "active" ? (
        <section className="panel">
          <h2>Activation Complete</h2>
          <button type="button" onClick={() => router.push(`/experiment/${testDesignId}/delayed`)}>
            Open Delayed Test
          </button>
        </section>
      ) : next ? (
        <section className="panel" aria-live="polite">
          <p>
            Item {next.assignment_order} of {next.total_assignment_count}
          </p>
          <article className="word-card">
            <p className="korean-word">{next.korean}</p>
            <p>{next.english_answer}</p>
            <p>Target interval: {formatDuration(next.interval_seconds)}</p>
          </article>
          <button type="button" onClick={completeCurrent} disabled={submitting}>
            {submitting ? "Recording..." : "I Have Reviewed This Word"}
          </button>
        </section>
      ) : null}
    </ExperimentShell>
  );
}
