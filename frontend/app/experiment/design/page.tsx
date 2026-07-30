"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { ExperimentShell } from "@/components/experiment/ExperimentShell";
import { ErrorPanel, LoadingPanel } from "@/components/ui/StatusPanels";
import { createTestDesign, getTestDesign, startLearning } from "@/lib/api/test-designs";
import type { TestDesign } from "@/lib/api/types";
import { DEVELOPMENT_INTERVALS, RESEARCH_INTERVALS, validateDesignInput } from "@/lib/design-validation";
import { clearParticipantSession, readParticipantSession, type ParticipantSession } from "@/lib/participant-session";
import { formatDuration } from "@/lib/time-format";

function DesignPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [itemsPerGroup, setItemsPerGroup] = useState(4);
  const [intervalText, setIntervalText] = useState(DEVELOPMENT_INTERVALS.join(", "));
  const [draft, setDraft] = useState<TestDesign | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const validation = useMemo(() => validateDesignInput(itemsPerGroup, intervalText), [itemsPerGroup, intervalText]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const stored = readParticipantSession();
      setSession(stored);
      const draftId = Number(searchParams.get("testDesignId"));
      if (Number.isInteger(draftId) && draftId > 0) {
        setLoading(true);
        getTestDesign(draftId)
          .then(setDraft)
          .catch((error: unknown) =>
            setMessage(error instanceof Error ? error.message : "Could not load the draft design."),
          )
          .finally(() => setLoading(false));
      }
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [searchParams]);

  function clearSession() {
    clearParticipantSession();
    router.push("/");
  }

  async function handleCreate() {
    if (!session || !validation.valid) return;
    setLoading(true);
    setMessage(null);
    try {
      const created = await createTestDesign({
        participant_id: session.participantId,
        items_per_group: itemsPerGroup,
        intervals_seconds: validation.intervals,
      });
      setDraft(created);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create the design.");
    } finally {
      setLoading(false);
    }
  }

  async function handleStartLearning() {
    if (!draft) return;
    setLoading(true);
    setMessage(null);
    try {
      await startLearning(draft.id);
      router.push(`/experiment/${draft.id}/learn`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not start learning.");
    } finally {
      setLoading(false);
    }
  }

  if (!session) {
    return (
      <ExperimentShell session={session} title="Create Experiment" onClearSession={clearSession}>
        <ErrorPanel message="The participant session could not be found." />
      </ExperimentShell>
    );
  }

  return (
    <ExperimentShell session={session} title="Create Experiment" onClearSession={clearSession}>
      {loading ? <LoadingPanel message="Working..." /> : null}
      <section className="panel">
        <h2>Design Settings</h2>
        <div className="preset-row" aria-label="Interval presets">
          <button type="button" className="secondary-button" onClick={() => setIntervalText(DEVELOPMENT_INTERVALS.join(", "))}>
            Development
          </button>
          <button type="button" className="secondary-button" onClick={() => setIntervalText(RESEARCH_INTERVALS.join(", "))}>
            Research
          </button>
        </div>
        <form className="form-grid" onSubmit={(event) => event.preventDefault()}>
          <label>
            Items per group
            <input
              type="number"
              min="1"
              value={itemsPerGroup}
              onChange={(event) => setItemsPerGroup(Number(event.target.value))}
            />
          </label>
          <label>
            Retention intervals in seconds
            <textarea value={intervalText} onChange={(event) => setIntervalText(event.target.value)} rows={4} />
          </label>
        </form>
        <dl className="summary-grid">
          <div>
            <dt>Group count</dt>
            <dd>{validation.groupCount}</dd>
          </div>
          <div>
            <dt>Required item count</dt>
            <dd>{validation.requiredItemCount}</dd>
          </div>
        </dl>
        <p>This experiment requires mastering {validation.requiredItemCount} vocabulary items.</p>
        <ul className="plain-list">
          {validation.intervals.map((interval) => (
            <li key={interval}>
              {interval} seconds: {formatDuration(interval)}
            </li>
          ))}
        </ul>
        {validation.errors.length ? (
          <ul className="error-list" role="alert">
            {validation.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        ) : null}
        <button type="button" onClick={handleCreate} disabled={loading || !validation.valid || !!draft}>
          Create Draft Design
        </button>
      </section>
      {draft ? (
        <section className="panel" aria-live="polite">
          <h2>Draft Created</h2>
          <p>Stored random seed: {draft.random_seed}</p>
          <button type="button" onClick={handleStartLearning} disabled={loading}>
            Start Learning
          </button>
        </section>
      ) : null}
      {message ? <ErrorPanel message={message} /> : null}
    </ExperimentShell>
  );
}

export default function DesignPage() {
  return (
    <Suspense fallback={<LoadingPanel message="Loading design page..." />}>
      <DesignPageContent />
    </Suspense>
  );
}
