import { API_BASE } from "./client";

export interface SocketTicket {
  ticket: string;
  websocket_path: string;
  conversation_id: number | null;
  conversation_token?: string | null;
  expires_in: number;
}

export interface LiveMessage {
  id: number;
  client_message_id: string | null;
  role: "user" | "assistant";
  content: string;
  sender_type: "visitor" | "operator" | "ai" | "system";
  sender_user_id: string | null;
  sender_display_name: string | null;
  created_at: string;
}

export interface LiveState {
  conversation_id: number;
  profile_id: number;
  mode: "ai" | "waiting" | "human" | "pending_ticket" | "closed";
  assigned_user_id: string | null;
  escalation_requested_at: string | null;
  escalation_expires_at: string | null;
  accepted_at: string | null;
  closed_at: string | null;
  messages?: LiveMessage[];
}

async function json<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
  return body as T;
}

export async function operatorSocketTicket(
  siteId: number,
  channel: "inbox" | "conversation",
  conversationId?: number,
): Promise<SocketTicket> {
  return json(
    await fetch(`${API_BASE}/live/operator/socket-ticket`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        site_id: siteId,
        channel,
        conversation_id: conversationId,
      }),
    }),
  );
}

export function openLiveSocket(ticket: SocketTicket): WebSocket {
  const url = new URL(ticket.websocket_path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(url, ["live-v1", `ticket.${ticket.ticket}`]);
}

export const callbacksKey = (siteId: number) => `live-callbacks:${siteId}`;
export const operatorsKey = (siteId: number) => `live-operators:${siteId}`;

// Stored as "pending" but shown as the board's "New" column.
export type TicketStatus = "pending" | "in_progress" | "resolved";

export interface CallbackTicket {
  id: number;
  conversation_id: number;
  customer_name: string | null;
  customer_email: string;
  customer_message: string | null;
  status: TicketStatus;
  assignee_user_id: string | null;
  archived: boolean;
  created_at: string;
  resolved_at: string | null;
}

export interface Operator {
  user_id: string;
  email: string | null;
  is_owner: boolean;
}

export async function listCallbacks(siteId: number): Promise<CallbackTicket[]> {
  return json(await fetch(`${API_BASE}/live/callbacks?site_id=${siteId}`));
}

export async function listOperators(siteId: number): Promise<Operator[]> {
  return json(await fetch(`${API_BASE}/live/operators?site_id=${siteId}`));
}

async function postCallbackAction(
  siteId: number,
  ticketId: number,
  action: string,
  body: unknown,
): Promise<CallbackTicket> {
  return json(
    await fetch(`${API_BASE}/live/callbacks/${ticketId}/${action}?site_id=${siteId}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export async function setCallbackStatus(
  siteId: number,
  ticketId: number,
  status: TicketStatus,
): Promise<CallbackTicket> {
  return postCallbackAction(siteId, ticketId, "status", { status });
}

export async function assignCallback(
  siteId: number,
  ticketId: number,
  assigneeUserId: string | null,
): Promise<CallbackTicket> {
  return postCallbackAction(siteId, ticketId, "assignee", { assignee_user_id: assigneeUserId });
}

export async function archiveCallback(
  siteId: number,
  ticketId: number,
  archived: boolean,
): Promise<CallbackTicket> {
  return postCallbackAction(siteId, ticketId, "archive", { archived });
}
