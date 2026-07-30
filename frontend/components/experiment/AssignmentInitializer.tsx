"use client";

import { useState } from "react";

import { initializeAssignments } from "@/lib/api/assignments";
import type { AssignmentInitialization } from "@/lib/api/types";
import { formatDuration } from "@/lib/time-format";

export function AssignmentInitializer({
  testDesignId,
  onInitialized,
}: {
  testDesignId: number;
  onInitialized: (result: AssignmentInitialization) => void;
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleInitialize() {
    setIsSubmitting(true);
    setMessage(null);
    try {
      const result = await initializeAssignments(testDesignId);
      onInitialized(result);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not initialize test groups.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="panel" aria-live="polite">
      <h2>Initialize Test Groups</h2>
      <p>
        Mastered words will be assigned evenly to the retention intervals. This prepares the final review stage and
        does not reveal the shuffled item IDs.
      </p>
      {message ? <p className="error-text">{message}</p> : null}
      <button type="button" onClick={handleInitialize} disabled={isSubmitting}>
        {isSubmitting ? "Initializing..." : "Initialize Test Groups"}
      </button>
    </section>
  );
}

export function AssignmentInitializationSummary({ result }: { result: AssignmentInitialization }) {
  return (
    <section className="panel">
      <h2>Groups Created</h2>
      <dl className="summary-grid">
        <div>
          <dt>Total assignments</dt>
          <dd>{result.assignment_count}</dd>
        </div>
        <div>
          <dt>Group count</dt>
          <dd>{result.group_count}</dd>
        </div>
      </dl>
      <ul className="plain-list">
        {result.groups.map((group) => (
          <li key={group.test_design_group_id}>
            Group {group.group_index}: {group.assignment_count} words at {formatDuration(group.interval_seconds)}
          </li>
        ))}
      </ul>
    </section>
  );
}
