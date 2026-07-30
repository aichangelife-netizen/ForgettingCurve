import { apiRequest } from "./client";
import type { TestDesign } from "./types";

export type TestDesignCreatePayload = {
  participant_id: number;
  items_per_group: number;
  intervals_seconds: number[];
};

export function createTestDesign(payload: TestDesignCreatePayload, signal?: AbortSignal): Promise<TestDesign> {
  return apiRequest<TestDesign>("/api/test-designs", { method: "POST", body: payload, signal });
}

export function getTestDesign(testDesignId: number, signal?: AbortSignal): Promise<TestDesign> {
  return apiRequest<TestDesign>(`/api/test-designs/${testDesignId}`, { signal });
}

export function startLearning(testDesignId: number, signal?: AbortSignal): Promise<TestDesign> {
  return apiRequest<TestDesign>(`/api/test-designs/${testDesignId}/start-learning`, {
    method: "POST",
    body: {},
    signal,
  });
}
