import { apiRequest } from "./client";
import type { Participant, ParticipantRetentionHistory, TestDesign } from "./types";

export function createParticipant(signal?: AbortSignal): Promise<Participant> {
  return apiRequest<Participant>("/api/participants", { method: "POST", body: {}, signal });
}

export function getParticipant(participantId: number, signal?: AbortSignal): Promise<Participant> {
  return apiRequest<Participant>(`/api/participants/${participantId}`, { signal });
}

export function getCurrentTestDesign(participantId: number, signal?: AbortSignal): Promise<TestDesign> {
  return apiRequest<TestDesign>(`/api/participants/${participantId}/test-designs/current`, { signal });
}

export function getParticipantRetentionHistory(
  participantId: number,
  signal?: AbortSignal,
): Promise<ParticipantRetentionHistory> {
  return apiRequest<ParticipantRetentionHistory>(`/api/participants/${participantId}/retention-history`, { signal });
}
