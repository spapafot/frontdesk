export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

// WebSocket origin derived from API_BASE (http -> ws, https -> wss).
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// Public Terms of Service URL (marketing site), linked from in-app disclaimers.
export const TERMS_URL =
  (import.meta.env.VITE_TERMS_URL as string | undefined) ??
  "https://plugandplay.gr/terms-of-service";

/** An error carrying the HTTP status, so callers can branch on it (e.g. a 402
 * plan-limit response drives an "upgrade" prompt). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** True when the error is a 402 (plan limit reached / payment required). */
export function isPlanLimitError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 402;
}

/** The backend's distinct 401 detail for "valid token, but this MFA-enrolled
 * account must present an aal2 session" (see require_admin in core/auth.py). */
export const MFA_REQUIRED_DETAIL = "mfa_required";

/** Parse a fetch Response, throwing ApiError with the backend's detail message
 * (and status) on failure. Shared by the api/* modules. */
export async function parse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail && typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON body; keep the generic message
    }
    if (response.status === 401 && detail === MFA_REQUIRED_DETAIL) {
      // The session lost its MFA verification (e.g. enrollment in another tab,
      // or a re-login mid-flow). A reload remounts AuthGate, which re-checks
      // the assurance level and shows the code challenge; it cannot loop
      // because the gate blocks until the challenge passes.
      window.location.reload();
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}
