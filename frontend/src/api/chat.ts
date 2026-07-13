import { API_BASE } from "./client";

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
}

export interface Source {
  title: string | null;
  score: number | null;
  snippet: string;
}

export type StreamEvent =
  | { type: "conversation"; conversation_id: number }
  | { type: "tool_call"; name: string; arguments: Record<string, unknown>; result: unknown }
  | { type: "sources"; sources: Source[] }
  | { type: "token"; content: string }
  | { type: "done"; conversation_id: number }
  | { type: "error"; message: string };

export interface ChatRequest {
  message: string;
  conversationId: number | null;
  siteId: number | null;
}

export async function streamChat(
  { message, conversationId, siteId }: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      site_id: siteId,
    }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separator: number;
    while ((separator = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separator).trim();
      buffer = buffer.slice(separator + 2);
      if (!rawEvent.startsWith("data:")) continue;
      const json = rawEvent.slice(rawEvent.indexOf("data:") + 5).trim();
      if (!json) continue;
      try {
        onEvent(JSON.parse(json) as StreamEvent);
      } catch {
        // Ignore malformed partial events.
      }
    }
  }
}
