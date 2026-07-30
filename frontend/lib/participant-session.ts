export type ParticipantSession = {
  participantId: number;
  participantCode: string;
};

const STORAGE_KEY = "forgetting_curve_participant_session";

function isParticipantSession(value: unknown): value is ParticipantSession {
  if (!value || typeof value !== "object") return false;
  const candidate = value as { participantId?: unknown; participantCode?: unknown };
  return (
    typeof candidate.participantId === "number" &&
    Number.isInteger(candidate.participantId) &&
    candidate.participantId > 0 &&
    typeof candidate.participantCode === "string" &&
    candidate.participantCode.length > 0
  );
}

function storage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

export function readParticipantSession(): ParticipantSession | null {
  const localStorage = storage();
  if (!localStorage) return null;
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (isParticipantSession(parsed)) return parsed;
  } catch {
    // Corrupted local MVP session data is cleared below.
  }
  localStorage.removeItem(STORAGE_KEY);
  return null;
}

export function saveParticipantSession(session: ParticipantSession): void {
  const localStorage = storage();
  if (!localStorage) return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearParticipantSession(): void {
  const localStorage = storage();
  if (!localStorage) return;
  localStorage.removeItem(STORAGE_KEY);
}

export const participantSessionStorageKey = STORAGE_KEY;
