import { apiRequest } from "./client";
import type { CurveCreateResponse, CurveDetail, CurveEligibility, CurveList } from "./types";

export function getCurveEligibility(testDesignId: number, signal?: AbortSignal): Promise<CurveEligibility> {
  return apiRequest<CurveEligibility>(`/api/test-designs/${testDesignId}/curve-eligibility`, { signal });
}

export function createCurveModel(testDesignId: number, signal?: AbortSignal): Promise<CurveCreateResponse> {
  return apiRequest<CurveCreateResponse>(`/api/test-designs/${testDesignId}/curve-model`, {
    method: "POST",
    body: {},
    signal,
  });
}

export function listCurveModels(participantId: number, signal?: AbortSignal): Promise<CurveList> {
  return apiRequest<CurveList>(`/api/participants/${participantId}/curve-models`, { signal });
}

export function getLatestCurveModel(participantId: number, signal?: AbortSignal): Promise<CurveDetail> {
  return apiRequest<CurveDetail>(`/api/participants/${participantId}/curve-models/latest`, { signal });
}

export function getCurveModelVersion(
  participantId: number,
  version: number,
  signal?: AbortSignal,
): Promise<CurveDetail> {
  return apiRequest<CurveDetail>(`/api/participants/${participantId}/curve-models/${version}`, { signal });
}
