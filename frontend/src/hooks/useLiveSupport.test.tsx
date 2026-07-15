import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useLiveConversation } from "./useLiveSupport";

const api = vi.hoisted(() => ({
  operatorSocketTicket: vi.fn(),
  openLiveSocket: vi.fn(),
}));

vi.mock("../api/live", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/live")>()),
  operatorSocketTicket: api.operatorSocketTicket,
  openLiveSocket: api.openLiveSocket,
}));

class FakeSocket {
  readyState = WebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
}

afterEach(() => {
  vi.restoreAllMocks();
  api.operatorSocketTicket.mockReset();
  api.openLiveSocket.mockReset();
});

describe("useLiveConversation", () => {
  it("preserves the snapshot through acceptance and merges messages by id", async () => {
    const socket = new FakeSocket();
    api.operatorSocketTicket.mockResolvedValue({
      ticket: "ticket",
      websocket_path: "/live/conversations/11",
      conversation_id: 11,
      expires_in: 60,
    });
    api.openLiveSocket.mockReturnValue(socket as unknown as WebSocket);

    const { result } = renderHook(() => useLiveConversation(1, 11, true));
    await waitFor(() => expect(socket.onmessage).not.toBeNull());
    const visitor = {
      id: 1,
      client_message_id: null,
      role: "user" as const,
      content: "I need help",
      sender_type: "visitor" as const,
      sender_user_id: null,
      sender_display_name: null,
      created_at: "2026-07-14T08:00:00Z",
    };

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "state",
          conversation_id: 11,
          profile_id: 1,
          mode: "waiting",
          messages: [visitor],
        }),
      } as MessageEvent);
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "state",
          conversation_id: 11,
          profile_id: 1,
          mode: "human",
          assigned_user_id: "owner-1",
        }),
      } as MessageEvent);
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "message",
          message: visitor,
        }),
      } as MessageEvent);
    });

    expect(result.current.state?.mode).toBe("human");
    expect(result.current.state?.messages).toEqual([visitor]);
  });

  it("does not reconnect after receiving the terminal closed state", async () => {
    const socket = new FakeSocket();
    api.operatorSocketTicket.mockResolvedValue({
      ticket: "ticket",
      websocket_path: "/live/conversations/11",
      conversation_id: 11,
      expires_in: 60,
    });
    api.openLiveSocket.mockReturnValue(socket as unknown as WebSocket);
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");

    const { result } = renderHook(() => useLiveConversation(1, 11, true));
    await waitFor(() => expect(socket.onmessage).not.toBeNull());

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "state",
          conversation_id: 11,
          profile_id: 1,
          mode: "closed",
        }),
      } as MessageEvent);
      socket.onclose?.();
    });

    expect(result.current.state?.mode).toBe("closed");
    expect(setTimeoutSpy).not.toHaveBeenCalledWith(expect.any(Function), 1500);
  });
});
