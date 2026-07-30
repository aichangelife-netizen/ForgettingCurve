"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CurveChart } from "@/components/curve/CurveChart";
import { ExperimentShell } from "@/components/experiment/ExperimentShell";
import { ErrorPanel, LoadingPanel } from "@/components/ui/StatusPanels";
import { ApiError } from "@/lib/api/client";
import { createCurveModel, getCurveEligibility, getCurveModelVersion, listCurveModels } from "@/lib/api/curves";
import { getRetentionSummary } from "@/lib/api/delayed-recall";
import type { CurveDetail, CurveEligibility, CurveList, RetentionSummary } from "@/lib/api/types";
import { clearParticipantSession, readParticipantSession, type ParticipantSession } from "@/lib/participant-session";
import { formatDateTime, formatDuration, formatPercentage } from "@/lib/time-format";

function reasonText(reason: string): string {
  return reason.replaceAll("_", " ");
}

export default function ResultsPage() {
  const router = useRouter();
  const params = useParams<{ testDesignId: string }>();
  const testDesignId = Number(params.testDesignId);
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [summary, setSummary] = useState<RetentionSummary | null>(null);
  const [eligibility, setEligibility] = useState<CurveEligibility | null>(null);
  const [history, setHistory] = useState<CurveList | null>(null);
  const [selectedCurve, setSelectedCurve] = useState<CurveDetail | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const stored = readParticipantSession();
    setSession(stored);
    setLoading(true);
    setMessage(null);
    try {
      const loadedSummary = await getRetentionSummary(testDesignId);
      setSummary(loadedSummary);
      const loadedEligibility = loadedSummary.status === "completed" ? await getCurveEligibility(testDesignId) : null;
      setEligibility(loadedEligibility);
      if (stored) {
        const loadedHistory = await listCurveModels(stored.participantId);
        setHistory(loadedHistory);
        const latest = loadedHistory.curves.at(-1);
        if (latest) {
          setSelectedVersion(latest.version);
          setSelectedCurve(await getCurveModelVersion(stored.participantId, latest.version));
        } else {
          setSelectedVersion(null);
          setSelectedCurve(null);
        }
      }
    } catch (error) {
      if (error instanceof ApiError && error.kind === "not_found") {
        setMessage("The requested result could not be found.");
      } else {
        setMessage(error instanceof Error ? error.message : "Could not load results.");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testDesignId]);

  async function generateCurve() {
    if (submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const created = await createCurveModel(testDesignId);
      setSelectedCurve(created);
      setSelectedVersion(created.curve.version);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not generate the personal curve.");
    } finally {
      setSubmitting(false);
    }
  }

  async function selectVersion(version: number) {
    if (!session) return;
    setSelectedVersion(version);
    setLoading(true);
    try {
      setSelectedCurve(await getCurveModelVersion(session.participantId, version));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load the selected curve version.");
    } finally {
      setLoading(false);
    }
  }

  function clearSession() {
    clearParticipantSession();
    router.push("/");
  }

  return (
    <ExperimentShell session={session} title="Results" onClearSession={clearSession}>
      {loading ? <LoadingPanel message="Loading results..." /> : null}
      {message ? <ErrorPanel message={message} onRetry={load} /> : null}
      {summary ? (
        <section className="panel">
          <h2>Raw Retention Results</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Target interval</th>
                  <th>Status</th>
                  <th>Completed</th>
                  <th>Correct</th>
                  <th>Incorrect</th>
                  <th>Accuracy</th>
                  <th>Mean actual time</th>
                  <th>Range</th>
                  <th>Time point</th>
                </tr>
              </thead>
              <tbody>
                {summary.groups.map((group) => (
                  <tr key={group.test_design_group_id}>
                    <td>{formatDuration(group.target_interval_seconds)}</td>
                    <td>{group.status}</td>
                    <td>
                      {group.completed_count} / {group.assignment_count}
                    </td>
                    <td>{group.correct_count ?? "Not available"}</td>
                    <td>{group.incorrect_count ?? "Not available"}</td>
                    <td>{formatPercentage(group.observed_accuracy)}</td>
                    <td>
                      {group.mean_actual_retention_seconds === null
                        ? "Not available"
                        : formatDuration(group.mean_actual_retention_seconds)}
                    </td>
                    <td>
                      {group.minimum_actual_retention_seconds === null || group.maximum_actual_retention_seconds === null
                        ? "Not available"
                        : `${formatDuration(group.minimum_actual_retention_seconds)} to ${formatDuration(
                            group.maximum_actual_retention_seconds,
                          )}`}
                    </td>
                    <td>{group.status === "completed" ? "Complete time point" : "Partial time point"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      {summary && summary.complete_time_point_count < 5 ? (
        <section className="panel">
          <h2>Official Curve</h2>
          <p>Insufficient data for an official personal curve. Five complete time points are required.</p>
        </section>
      ) : null}
      {eligibility ? (
        <section className="panel">
          <h2>Curve Eligibility</h2>
          <dl className="summary-grid">
            <div>
              <dt>Eligible</dt>
              <dd>{eligibility.eligible ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt>Complete time points</dt>
              <dd>{eligibility.complete_time_point_count}</dd>
            </div>
            <div>
              <dt>Sample count</dt>
              <dd>{eligibility.sample_count}</dd>
            </div>
          </dl>
          {eligibility.reasons.length ? (
            <ul className="plain-list">
              {eligibility.reasons.map((reason) => (
                <li key={reason}>{reasonText(reason)}</li>
              ))}
            </ul>
          ) : null}
          {eligibility.eligible && !eligibility.has_existing_curve ? (
            <button type="button" onClick={generateCurve} disabled={submitting}>
              {submitting ? "Generating..." : "Generate Personal Curve"}
            </button>
          ) : null}
        </section>
      ) : null}
      {history && history.curves.length ? (
        <section className="panel">
          <h2>Curve Version History</h2>
          <label>
            Select version
            <select
              value={selectedVersion ?? ""}
              onChange={(event) => void selectVersion(Number(event.target.value))}
            >
              {history.curves.map((curve) => (
                <option key={curve.version} value={curve.version}>
                  {curve.display_name}
                </option>
              ))}
            </select>
          </label>
          <ul className="plain-list">
            {history.curves.map((curve) => (
              <li key={curve.version}>
                {curve.display_name}: trigger design {curve.trigger_test_design_id}, fitted {formatDateTime(curve.fitted_at)},{" "}
                {curve.sample_count} samples
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {selectedCurve ? (
        <>
          <section className="panel">
            <h2>{selectedCurve.curve.display_name}</h2>
            <p>
              {selectedCurve.curve.version === selectedVersion ? "Historical snapshot." : "Official curve."} Older
              versions are read-only and are not refitted.
            </p>
            <dl className="summary-grid">
              <div>
                <dt>T seconds</dt>
                <dd>
                  {selectedCurve.curve.T_seconds.toFixed(2)} seconds ({formatDuration(selectedCurve.curve.T_seconds)})
                </dd>
              </div>
              <div>
                <dt>c</dt>
                <dd>{selectedCurve.curve.c.toFixed(4)}</dd>
              </div>
              <div>
                <dt>Sample count</dt>
                <dd>{selectedCurve.curve.sample_count}</dd>
              </div>
              <div>
                <dt>Complete time points</dt>
                <dd>{selectedCurve.curve.complete_time_point_count}</dd>
              </div>
              <div>
                <dt>Fitted at</dt>
                <dd>{formatDateTime(selectedCurve.curve.fitted_at)}</dd>
              </div>
            </dl>
            <p>
              T is a fitted time-scale parameter, and c controls curve shape. Neither parameter is an independently
              observed memory score.
            </p>
            {selectedCurve.warnings.length ? (
              <ul className="plain-list">
                {selectedCurve.warnings.map((warning) => (
                  <li key={warning}>{reasonText(warning)}</li>
                ))}
              </ul>
            ) : (
              <p>No fitting warnings were returned.</p>
            )}
          </section>
          <CurveChart observedPoints={selectedCurve.observed_points} predictedPoints={selectedCurve.predicted_points} />
          <section className="panel">
            <h2>Observed Point Details</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Target interval</th>
                    <th>Mean actual time</th>
                    <th>Correct / total</th>
                    <th>Observed accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedCurve.observed_points.map((point) => (
                    <tr key={`${point.test_design_id}-${point.test_design_group_id}`}>
                      <td>{formatDuration(point.target_interval_seconds)}</td>
                      <td>{formatDuration(point.mean_actual_retention_seconds)}</td>
                      <td>
                        {point.correct_count} / {point.total_count}
                      </td>
                      <td>{formatPercentage(point.observed_accuracy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </ExperimentShell>
  );
}
