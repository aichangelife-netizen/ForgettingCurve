"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { getLatestCurveModel } from "@/lib/api/curves";
import { ApiError } from "@/lib/api/client";
import { getCurrentTestDesign, getParticipant, getParticipantRetentionHistory } from "@/lib/api/participants";
import type { CurveDetail, Participant, ParticipantRetentionDesign, TestDesign } from "@/lib/api/types";
import { AssignmentInitializer, AssignmentInitializationSummary } from "@/components/experiment/AssignmentInitializer";
import { ExperimentShell } from "@/components/experiment/ExperimentShell";
import { ErrorPanel, LoadingPanel } from "@/components/ui/StatusPanels";
import { clearParticipantSession, readParticipantSession, type ParticipantSession } from "@/lib/participant-session";
import { formatDateTime } from "@/lib/time-format";

function actionForDesign(design: TestDesign): { href?: string; label: string } {
  if (design.status === "draft") return { href: `/experiment/design?testDesignId=${design.id}`, label: "Continue to Design" };
  if (design.status === "learning") return { href: `/experiment/${design.id}/learn`, label: "Continue Learning" };
  if (design.status === "activation_review") {
    return { href: `/experiment/${design.id}/activation`, label: "Continue Activation Review" };
  }
  if (design.status === "active") return { href: `/experiment/${design.id}/delayed`, label: "Open Delayed Test" };
  if (design.status === "completed") return { href: `/experiment/${design.id}/results`, label: "View Results" };
  return { label: "No action available" };
}

export default function ExperimentDashboard() {
  const router = useRouter();
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [participant, setParticipant] = useState<Participant | null>(null);
  const [design, setDesign] = useState<TestDesign | null>(null);
  const [latestCompletedDesign, setLatestCompletedDesign] = useState<ParticipantRetentionDesign | null>(null);
  const [latestCurve, setLatestCurve] = useState<CurveDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState<React.ComponentProps<typeof AssignmentInitializationSummary>["result"] | null>(null);

  async function load() {
    const stored = readParticipantSession();
    setSession(stored);
    if (!stored) {
      setLoading(false);
      setError("The participant session could not be found.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const foundParticipant = await getParticipant(stored.participantId);
      setParticipant(foundParticipant);
      try {
        setDesign(await getCurrentTestDesign(stored.participantId));
        setLatestCompletedDesign(null);
      } catch (currentError) {
        if (currentError instanceof ApiError && currentError.code === "current_test_design_not_found") {
          setDesign(null);
          const history = await getParticipantRetentionHistory(stored.participantId);
          setLatestCompletedDesign(history.designs.filter((item) => item.status === "completed").at(-1) ?? null);
        } else {
          throw currentError;
        }
      }
      try {
        setLatestCurve(await getLatestCurveModel(stored.participantId));
      } catch (curveError) {
        if (!(curveError instanceof ApiError && curveError.kind === "not_found")) throw curveError;
        setLatestCurve(null);
      }
    } catch (loadError) {
      if (loadError instanceof ApiError && loadError.code === "participant_not_found") {
        clearParticipantSession();
        setSession(null);
        setError("The participant session could not be found.");
      } else {
        setError(loadError instanceof Error ? loadError.message : "Could not load the experiment dashboard.");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, []);

  function clearSession() {
    clearParticipantSession();
    router.push("/");
  }

  if (loading) {
    return (
      <ExperimentShell session={session} title="Experiment Dashboard" onClearSession={clearSession}>
        <LoadingPanel message="Loading participant state..." />
      </ExperimentShell>
    );
  }

  if (error || !session || !participant) {
    return (
      <ExperimentShell session={session} title="Experiment Dashboard" onClearSession={clearSession}>
        <ErrorPanel message={error ?? "The participant session could not be found."} onRetry={load} />
        <Link className="secondary-button" href="/">
          Return Home
        </Link>
      </ExperimentShell>
    );
  }

  const action = design ? actionForDesign(design) : null;

  return (
    <ExperimentShell session={session} title="Experiment Dashboard" onClearSession={clearSession}>
      <section className="panel">
        <h2>Participant</h2>
        <dl className="summary-grid">
          <div>
            <dt>Code</dt>
            <dd>{participant.participant_code}</dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{formatDateTime(participant.created_at)}</dd>
          </div>
        </dl>
      </section>
      <section className="panel">
        <h2>Current Experiment</h2>
        {design ? (
          <>
            <dl className="summary-grid">
              <div>
                <dt>Status</dt>
                <dd>{design.status.replace("_", " ")}</dd>
              </div>
              <div>
                <dt>Required items</dt>
                <dd>{design.required_item_count}</dd>
              </div>
              <div>
                <dt>Groups</dt>
                <dd>{design.group_count}</dd>
              </div>
            </dl>
            <div className="button-row">
              {action?.href ? (
                <Link className="primary-button" href={action.href}>
                  {action.label}
                </Link>
              ) : null}
              {design.status === "assigning" ? (
                <AssignmentInitializer
                  testDesignId={design.id}
                  onInitialized={(result) => {
                    setInitialized(result);
                    router.push(`/experiment/${design.id}/activation`);
                  }}
                />
              ) : null}
            </div>
          </>
        ) : (
          <>
            {latestCompletedDesign ? (
              <dl className="summary-grid">
                <div>
                  <dt>Status</dt>
                  <dd>completed</dd>
                </div>
                <div>
                  <dt>Completed time points</dt>
                  <dd>{latestCompletedDesign.complete_time_point_count}</dd>
                </div>
              </dl>
            ) : (
              <p>No unfinished experiment is active for this participant.</p>
            )}
            <div className="button-row">
              {latestCompletedDesign ? (
                <Link className="primary-button" href={`/experiment/${latestCompletedDesign.test_design_id}/results`}>
                  View Results
                </Link>
              ) : null}
              <Link className="secondary-button" href="/experiment/design">
                Create New Experiment
              </Link>
            </div>
          </>
        )}
      </section>
      {initialized ? <AssignmentInitializationSummary result={initialized} /> : null}
      <section className="panel">
        <h2>Latest Official Curve</h2>
        {latestCurve ? (
          <p>
            {latestCurve.curve.display_name} fitted at {formatDateTime(latestCurve.curve.fitted_at)} with{" "}
            {latestCurve.curve.sample_count} delayed-recall items.
          </p>
        ) : (
          <p>No official personal curve exists yet.</p>
        )}
      </section>
    </ExperimentShell>
  );
}
