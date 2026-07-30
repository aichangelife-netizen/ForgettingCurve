"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ExperimentShell } from "@/components/experiment/ExperimentShell";
import { ProgressMeter } from "@/components/experiment/ProgressMeter";
import { ErrorPanel, LoadingPanel } from "@/components/ui/StatusPanels";
import { getDelayedRecallProgress, getNextDelayedRecall, submitDelayedRecall } from "@/lib/api/delayed-recall";
import type { DelayedRecallProgress, NextDelayedRecall } from "@/lib/api/types";
import { clearParticipantSession, readParticipantSession, type ParticipantSession } from "@/lib/participant-session";
import { formatCountdown, formatDateTime } from "@/lib/time-format";

export default function DelayedRecallPage() {
  const router = useRouter();
  const params = useParams<{ testDesignId: string }>();
  const testDesignId = Number(params.testDesignId);
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [progress, setProgress] = useState<DelayedRecallProgress | null>(null);
  const [next, setNext] = useState<NextDelayedRecall | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const questionStartedAt = useRef<number>(0);

  async function load() {
    setSession(readParticipantSession());
    setLoading(true);
    setMessage(null);
    try {
      const [loadedProgress, loadedNext] = await Promise.all([
        getDelayedRecallProgress(testDesignId),
        getNextDelayedRecall(testDesignId),
      ]);
      setProgress(loadedProgress);
      setNext(loadedNext);
      if (loadedProgress.status === "completed") {
        router.push(`/experiment/${testDesignId}/results`);
        return;
      }
      if (loadedNext.available) {
        questionStartedAt.current = performance.now();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load delayed test state.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    const interval = window.setInterval(() => {
      void load();
    }, 30000);
    return () => {
      window.clearTimeout(timeout);
      window.clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testDesignId]);

  async function handleSubmit() {
    if (!next?.assignment || submitting) return;
    setSubmitting(true);
    setMessage(null);
    setConfirmation(null);
    try {
      const elapsed = Math.max(0, Math.round(performance.now() - questionStartedAt.current));
      const result = await submitDelayedRecall(testDesignId, next.assignment.assignment_id, {
        user_answer: answer,
        response_time_ms: elapsed,
      });
      setAnswer("");
      setConfirmation("Response recorded.");
      if (result.design_status === "completed") {
        router.push(`/experiment/${testDesignId}/results`);
        return;
      }
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not submit the delayed response.");
    } finally {
      setSubmitting(false);
    }
  }

  function clearSession() {
    clearParticipantSession();
    router.push("/");
  }

  return (
    <ExperimentShell session={session} title="Delayed Test" onClearSession={clearSession}>
      {loading ? <LoadingPanel message="Loading delayed recall..." /> : null}
      {message ? <ErrorPanel message={message} onRetry={load} /> : null}
      {progress ? (
        <section className="panel" aria-live="polite">
          <h2>Delayed-Test Progress</h2>
          <ProgressMeter
            label="Completed assignments"
            value={progress.completed_assignment_count}
            total={progress.total_assignment_count}
          />
          <dl className="summary-grid">
            <div>
              <dt>Pending</dt>
              <dd>{progress.pending_assignment_count}</dd>
            </div>
            <div>
              <dt>Due now</dt>
              <dd>{progress.due_assignment_count}</dd>
            </div>
            <div>
              <dt>Completed time points</dt>
              <dd>
                {progress.completed_group_count} / {progress.total_group_count}
              </dd>
            </div>
            <div>
              <dt>Next scheduled test</dt>
              <dd>{formatDateTime(progress.next_scheduled_at)}</dd>
            </div>
          </dl>
        </section>
      ) : null}
      {next?.available && next.assignment ? (
        <section className="panel">
          <h2>Recall Prompt</h2>
          <p>Enter the English answer. Correctness is not shown during the active experiment.</p>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void handleSubmit();
            }}
          >
            <p className="korean-word">{next.assignment.korean}</p>
            <label>
              English answer
              <input value={answer} onChange={(event) => setAnswer(event.target.value)} autoFocus />
            </label>
            <button type="submit" disabled={submitting}>
              {submitting ? "Recording..." : "Submit Response"}
            </button>
          </form>
        </section>
      ) : (
        <section className="panel">
          <h2>No Test Due</h2>
          <p>No test is due right now.</p>
          <p>Next scheduled: {formatDateTime(next?.next_scheduled_at ?? null)}</p>
          <p>{formatCountdown(next?.next_scheduled_at ?? null)}</p>
          <button type="button" className="secondary-button" onClick={load}>
            Refresh
          </button>
        </section>
      )}
      {confirmation ? (
        <p className="status-text" role="status" aria-live="polite">
          {confirmation}
        </p>
      ) : null}
    </ExperimentShell>
  );
}
