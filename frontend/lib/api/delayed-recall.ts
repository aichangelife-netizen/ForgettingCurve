import { apiRequest } from "./client";
import type { DelayedRecallProgress, DelayedRecallSubmission, NextDelayedRecall, RetentionSummary } from "./types";

export function getNextDelayedRecall(testDesignId: number, signal?: AbortSignal): Promise<NextDelayedRecall> {
  return apiRequest<NextDelayedRecall>(`/api/test-designs/${testDesignId}/delayed-recalls/next`, { signal });
}

export function submitDelayedRecall(
  testDesignId: number,
  assignmentId: number,
  payload: { user_answer: string; response_time_ms: number | null },
  signal?: AbortSignal,
): Promise<DelayedRecallSubmission> {
  return apiRequest<DelayedRecallSubmission>(`/api/test-designs/${testDesignId}/delayed-recalls/${assignmentId}`, {
    method: "POST",
    body: payload,
    signal,
  });
}

export function getDelayedRecallProgress(testDesignId: number, signal?: AbortSignal): Promise<DelayedRecallProgress> {
  return apiRequest<DelayedRecallProgress>(`/api/test-designs/${testDesignId}/delayed-recalls/progress`, { signal });
}

export function getRetentionSummary(testDesignId: number, signal?: AbortSignal): Promise<RetentionSummary> {
  return apiRequest<RetentionSummary>(`/api/test-designs/${testDesignId}/retention-summary`, { signal });
}
