import { apiRequest } from "./client";
import type { ActivationCompletion, ActivationNext, ActivationProgress, AssignmentInitialization } from "./types";

export function initializeAssignments(testDesignId: number, signal?: AbortSignal): Promise<AssignmentInitialization> {
  return apiRequest<AssignmentInitialization>(`/api/test-designs/${testDesignId}/initialize-assignments`, {
    method: "POST",
    body: {},
    signal,
  });
}

export function getActivationProgress(testDesignId: number, signal?: AbortSignal): Promise<ActivationProgress> {
  return apiRequest<ActivationProgress>(`/api/test-designs/${testDesignId}/activation-review/progress`, { signal });
}

export function getActivationNext(testDesignId: number, signal?: AbortSignal): Promise<ActivationNext> {
  return apiRequest<ActivationNext>(`/api/test-designs/${testDesignId}/activation-review/next`, { signal });
}

export function completeActivationReview(
  testDesignId: number,
  assignmentId: number,
  signal?: AbortSignal,
): Promise<ActivationCompletion> {
  return apiRequest<ActivationCompletion>(`/api/test-designs/${testDesignId}/activation-review/${assignmentId}/complete`, {
    method: "POST",
    body: {},
    signal,
  });
}
