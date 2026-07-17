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

  it("tracks visitor typing and clears it when the visitor's message arrives", async () => {
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

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "state",
          conversation_id: 11,
          profile_id: 1,
          mode: "human",
        }),
      } as MessageEvent);
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "typing",
          actor_type: "visitor",
          typing: true,
        }),
      } as MessageEvent);
    });
    expect(result.current.visitorTyping).toBe(true);

    act(() => {
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "message",
          message: {
            id: 5,
            client_message_id: null,
            role: "user",
            content: "still there?",
            sender_type: "visitor",
            sender_user_id: null,
            sender_display_name: null,
            created_at: "2026-07-14T08:03:00Z",
          },
        }),
      } as MessageEvent);
    });
    expect(result.current.visitorTyping).toBe(false);
  });

  it("expires a stale typing signal and throttles outbound typing", async () => {
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

    vi.useFakeTimers();
    try {
      act(() => {
        socket.onmessage?.({
          data: JSON.stringify({
            version: 1,
            type: "typing",
            actor_type: "visitor",
            typing: true,
          }),
        } as MessageEvent);
      });
      expect(result.current.visitorTyping).toBe(true);

      // No refresh within the expiry window - the indicator hides on its own.
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      expect(result.current.visitorTyping).toBe(false);

      act(() => {
        result.current.notifyTyping(true);
        result.current.notifyTyping(true); // within the refresh window - dropped
        result.current.notifyTyping(false);
        result.current.notifyTyping(false); // already stopped - dropped
      });
      const sent = socket.send.mock.calls.map((call) => JSON.parse(call[0] as string));
      expect(sent).toEqual([
        { version: 1, type: "typing", typing: true },
        { version: 1, type: "typing", typing: false },
      ]);
    } finally {
      vi.useRealTimers();
    }
  });

  it("stops sending typing silently when an older Worker rejects the hint", async () => {
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

    act(() => {
      result.current.notifyTyping(true);
      socket.onmessage?.({
        data: JSON.stringify({
          version: 1,
          type: "error",
          message: "Unsupported live action.",
        }),
      } as MessageEvent);
      result.current.notifyTyping(false);
    });

    // The legacy rejection is swallowed (no operator-facing error) and no
    // further typing frames go out on this connection.
    expect(result.current.error).toBeNull();
    expect(socket.send).toHaveBeenCalledTimes(1);
    expect(JSON.parse(socket.send.mock.calls[0][0] as string)).toEqual({
      version: 1,
      type: "typing",
      typing: true,
    });
  });
});
