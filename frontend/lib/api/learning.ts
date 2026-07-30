import { apiRequest } from "./client";
import type { LearningAttempt, LearningMaterials, LearningProgress, NextLearningCheck } from "./types";

export function getLearningMaterials(testDesignId: number, signal?: AbortSignal): Promise<LearningMaterials> {
  return apiRequest<LearningMaterials>(`/api/test-designs/${testDesignId}/learning-materials`, { signal });
}

export function getNextLearningCheck(testDesignId: number, signal?: AbortSignal): Promise<NextLearningCheck> {
  return apiRequest<NextLearningCheck>(`/api/test-designs/${testDesignId}/learning-checks/next`, { signal });
}

export function submitLearningAttempt(
  testDesignId: number,
  payload: { test_design_item_id: number; user_answer: string; response_time_ms: number | null },
  signal?: AbortSignal,
): Promise<LearningAttempt> {
  return apiRequest<LearningAttempt>(`/api/test-designs/${testDesignId}/learning-attempts`, {
    method: "POST",
    body: payload,
    signal,
  });
}

export function getLearningProgress(testDesignId: number, signal?: AbortSignal): Promise<LearningProgress> {
  return apiRequest<LearningProgress>(`/api/test-designs/${testDesignId}/learning-progress`, { signal });
}
