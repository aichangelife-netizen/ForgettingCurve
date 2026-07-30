export type ApiErrorKind = "network" | "validation" | "conflict" | "not_found" | "server" | "unexpected";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status: number | null;
  code: string;

  constructor(kind: ApiErrorKind, message: string, options?: { status?: number | null; code?: string }) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options?.status ?? null;
    this.code = options?.code ?? kind;
  }
}

type JsonBody = Record<string, unknown> | unknown[] | null;

const FALLBACK_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return configured && configured.length > 0 ? configured.replace(/\/$/, "") : FALLBACK_API_BASE_URL;
}

function errorKindForStatus(status: number): ApiErrorKind {
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status >= 400 && status < 500) return "validation";
  if (status >= 500) return "server";
  return "unexpected";
}

function isBackendError(value: unknown): value is { detail: { code: string; message: string } } {
  if (!value || typeof value !== "object" || !("detail" in value)) return false;
  const detail = (value as { detail: unknown }).detail;
  return (
    !!detail &&
    typeof detail === "object" &&
    typeof (detail as { code?: unknown }).code === "string" &&
    typeof (detail as { message?: unknown }).message === "string"
  );
}

export async function parseApiError(response: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (isBackendError(payload)) {
    return new ApiError(errorKindForStatus(response.status), payload.detail.message, {
      status: response.status,
      code: payload.detail.code,
    });
  }
  return new ApiError(errorKindForStatus(response.status), `Request failed with status ${response.status}.`, {
    status: response.status,
    code: "unexpected_response",
  });
}

export async function apiRequest<T>(
  path: string,
  options: { method?: "GET" | "POST"; body?: JsonBody; signal?: AbortSignal } = {},
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: HeadersInit = {};
  let body: string | undefined;
  if (options.body !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      method,
      headers,
      body,
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("network", "The backend could not be reached.", { code: "network_failure" });
  }
  if (!response.ok) {
    throw await parseApiError(response);
  }
  return (await response.json()) as T;
}
