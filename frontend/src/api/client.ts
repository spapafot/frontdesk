export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

// WebSocket origin derived from API_BASE (http -> ws, https -> wss).
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// Public Terms of Service URL (marketing site), linked from in-app disclaimers.
export const TERMS_URL =
  (import.meta.env.VITE_TERMS_URL as string | undefined) ??
  "https://plugandplay.gr/terms-of-service";
