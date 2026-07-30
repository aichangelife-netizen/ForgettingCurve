"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AssignmentInitializer } from "@/components/experiment/AssignmentInitializer";
import { ExperimentShell } from "@/components/experiment/ExperimentShell";
import { ProgressMeter } from "@/components/experiment/ProgressMeter";
import { ErrorPanel, LoadingPanel } from "@/components/ui/StatusPanels";
import { getLearningMaterials, getLearningProgress, getNextLearningCheck, submitLearningAttempt } from "@/lib/api/learning";
import type { LearningAttempt, LearningMaterials, LearningProgress, NextLearningCheck } from "@/lib/api/types";
import { clearParticipantSession, readParticipantSession, type ParticipantSession } from "@/lib/participant-session";

export default function LearningPage() {
  const router = useRouter();
  const params = useParams<{ testDesignId: string }>();
  const testDesignId = Number(params.testDesignId);
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [mode, setMode] = useState<"study" | "check">("study");
  const [materials, setMaterials] = useState<LearningMaterials | null>(null);
  const [progress, setProgress] = useState<LearningProgress | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [check, setCheck] = useState<NextLearningCheck | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<LearningAttempt | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const questionStartedAt = useRef<number>(0);

  async function load() {
    if (!Number.isInteger(testDesignId) || testDesignId <= 0) {
      setMessage("The experiment ID is invalid.");
      setLoading(false);
      return;
    }
    setSession(readParticipantSession());
    setLoading(true);
    setMessage(null);
    try {
      const [loadedMaterials, loadedProgress] = await Promise.all([
        getLearningMaterials(testDesignId),
        getLearningProgress(testDesignId),
      ]);
      setMaterials(loadedMaterials);
      setProgress(loadedProgress);
      if (loadedProgress.status === "assigning") {
        setMode("check");
        setCheck(null);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load learning state.");
    } finally {
      setLoading(false);
    }
  }

  async function loadNextCheck() {
    setLoading(true);
    setMessage(null);
    setFeedback(null);
    setAnswer("");
    try {
      const loadedProgress = await getLearningProgress(testDesignId);
      setProgress(loadedProgress);
      if (loadedProgress.status === "assigning") {
        setCheck(null);
        return;
      }
      const next = await getNextLearningCheck(testDesignId);
      setCheck(next);
      questionStartedAt.current = performance.now();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load the next learning check.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testDesignId]);

  async function handleSubmit() {
    if (!check || submitting) return;
    setSubmitting(true);
    setMessage(null);
    try {
      const elapsed = Math.max(0, Math.round(performance.now() - questionStartedAt.current));
      const result = await submitLearningAttempt(testDesignId, {
        test_design_item_id: check.test_design_item_id,
        user_answer: answer,
        response_time_ms: elapsed,
      });
      setFeedback(result);
      setProgress((previous) =>
        previous
          ? {
              ...previous,
              status: result.design_status,
              mastered_item_count: result.mastered_item_count,
              remaining_item_count: result.remaining_item_count,
              total_attempt_count: previous.total_attempt_count + 1,
              correct_attempt_count: previous.correct_attempt_count + (result.is_correct ? 1 : 0),
            }
          : previous,
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not submit the learning answer.");
    } finally {
      setSubmitting(false);
    }
  }

  function beginChecks() {
    setMode("check");
    void loadNextCheck();
  }

  function clearSession() {
    clearParticipantSession();
    router.push("/");
  }

  return (
    <ExperimentShell session={session} title="Learning" onClearSession={clearSession}>
      {loading ? <LoadingPanel message="Loading learning workflow..." /> : null}
      {message ? <ErrorPanel message={message} onRetry={load} /> : null}
      {progress ? (
        <section className="panel" aria-live="polite">
          <h2>Mastery Progress</h2>
          <ProgressMeter label="Mastered words" value={progress.mastered_item_count} total={progress.required_item_count} />
          <dl className="summary-grid">
            <div>
              <dt>Remaining</dt>
              <dd>{progress.remaining_item_count}</dd>
            </div>
            <div>
              <dt>Total attempts</dt>
              <dd>{progress.total_attempt_count}</dd>
            </div>
            <div>
              <dt>Correct attempts</dt>
              <dd>{progress.correct_attempt_count}</dd>
            </div>
          </dl>
        </section>
      ) : null}
      {progress?.status === "assigning" ? (
        <>
          <section className="panel">
            <h2>Learning Complete</h2>
            <p>All required vocabulary items have been mastered. Initialize test groups when you are ready.</p>
          </section>
          <AssignmentInitializer testDesignId={testDesignId} onInitialized={() => router.push(`/experiment/${testDesignId}/activation`)} />
        </>
      ) : mode === "study" && materials ? (
        <section className="panel">
          <h2>Study Materials</h2>
          {materials.items.length ? (
            <>
              <p>
                Item {currentIndex + 1} of {materials.items.length}
              </p>
              <article className="word-card">
                <p className="korean-word">{materials.items[currentIndex].korean}</p>
                <p>{materials.items[currentIndex].english_answer}</p>
              </article>
              <div className="button-row">
                <button type="button" className="secondary-button" onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}>
                  Previous
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setCurrentIndex(Math.min(materials.items.length - 1, currentIndex + 1))}
                >
                  Next
                </button>
                <button type="button" onClick={beginChecks}>
                  Begin Learning Checks
                </button>
              </div>
            </>
          ) : (
            <p>No learning materials are available.</p>
          )}
        </section>
      ) : (
        <section className="panel">
          <h2>Learning Check</h2>
          {check && !feedback ? (
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void handleSubmit();
              }}
            >
              <p className="korean-word">{check.korean}</p>
              <label>
                English answer
                <input value={answer} onChange={(event) => setAnswer(event.target.value)} autoFocus />
              </label>
              <button type="submit" disabled={submitting}>
                {submitting ? "Submitting..." : "Submit Answer"}
              </button>
            </form>
          ) : null}
          {feedback ? (
            <div aria-live="polite">
              <p>{feedback.is_correct ? "Correct" : "Incorrect"}</p>
              <p>Canonical English answer: {feedback.canonical_answer}</p>
              <p>Consecutive correct count: {feedback.consecutive_correct_count}</p>
              <p>{feedback.is_mastered ? "This word is mastered." : "This word needs more practice."}</p>
              <button type="button" onClick={loadNextCheck}>
                Continue to Next Word
              </button>
            </div>
          ) : null}
        </section>
      )}
    </ExperimentShell>
  );
}
