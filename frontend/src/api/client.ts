export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

// WebSocket origin derived from API_BASE (http -> ws, https -> wss).
export const WS_BASE = API_BASE.replace(/^http/, "ws");
