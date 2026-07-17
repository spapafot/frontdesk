import { beforeEach, describe, expect, it, vi } from "vitest";

describe("embedded widget verification flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.resetModules();
    localStorage.clear();
    document.body.innerHTML = '<div id="app"></div>';
    history.replaceState(
      null,
      "",
      `/#${new URLSearchParams({
        origin: location.origin,
        api: "https://api.example",
        turnstileSiteKey: "site-key",
      })}`
    );
  });

  it("renders Turnstile on first open and sends its token only to the parent origin", async () => {
    let success: ((token: string) => void) | undefined;
    const render = vi.fn((_container, options) => {
      success = options.callback;
      return "widget-id";
    });
    window.turnstile = { render, reset: vi.fn() };
    const postMessage = vi.spyOn(window, "postMessage");

    await import("./app");
    window.dispatchEvent(new Event("load"));
    success?.("challenge-token");

    expect(render).toHaveBeenCalledWith(
      "#wx-turnstile",
      expect.objectContaining({
        sitekey: "site-key",
        action: "widget-session",
        size: "flexible",
      })
    );
    expect(postMessage).toHaveBeenCalledWith(
      { type: "wx-turnstile", token: "challenge-token" },
      location.origin
    );
  });

  it("keeps chat hidden until an origin-checked signed session arrives", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    await import("./app");

    const form = document.getElementById("wx-form") as HTMLFormElement;
    expect(form.hidden).toBe(true);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://attacker.example",
        source: window,
        data: { type: "wx-session", session: { token: "attacker" } },
      })
    );
    expect(form.hidden).toBe(true);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
          },
        },
      })
    );

    expect(form.hidden).toBe(false);
    expect(document.getElementById("wx-title")).toHaveTextContent("Helper");
  });

  it("keeps a stale conversation explicit and never creates a replacement", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Conversation not found." }), {
        status: 404,
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    class MockWebSocket {
      static OPEN = 1;
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(_url: string, _protocols: string[]) {
        queueMicrotask(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.();
        });
      }

      close() {}
      send() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "999");
    localStorage.setItem(`${storageKey}_token`, "stale-conversation-token");

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      conversation_id: 999,
      conversation_token: "stale-conversation-token",
    });
    expect(localStorage.getItem(storageKey)).toBe("999");
    expect(localStorage.getItem(`${storageKey}_token`)).toBe("stale-conversation-token");
  });

  it("recovers from an expired conversation session by starting a new conversation", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn(async () => {
      // The stored conversation session is expired: a refreshed widget token
      // still gets 401 (calls 1-2); the fresh-conversation retry succeeds.
      if (fetchMock.mock.calls.length <= 2) {
        return new Response(
          JSON.stringify({ detail: "Invalid or expired conversation session." }),
          { status: 401, headers: { "content-type": "application/json" } }
        );
      }
      return new Response(
        [
          `data: ${JSON.stringify({
            type: "conversation",
            conversation_id: 51,
            conversation_token: "fresh-token",
          })}`,
          `data: ${JSON.stringify({ type: "token", content: "Fresh answer" })}`,
          `data: ${JSON.stringify({ type: "done" })}`,
          "",
        ].join("\n\n"),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "999");
    localStorage.setItem(`${storageKey}_token`, "expired-conversation-token");

    const widget = await import("./app");
    const sessionMessage = (token: string) =>
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token,
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: false,
          },
        },
      });
    widget.handleParentMessage(sessionMessage("signed-session"));

    const postMessage = vi.spyOn(window, "postMessage");
    const form = document.getElementById("wx-form") as HTMLFormElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    input.value = "Hello again";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() =>
      expect(postMessage).toHaveBeenCalledWith({ type: "wx-refresh" }, location.origin)
    );
    widget.handleParentMessage(sessionMessage("signed-session-2"));

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      conversation_id: 999,
      conversation_token: "expired-conversation-token",
      widget_token: "signed-session-2",
    });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toMatchObject({
      conversation_id: null,
      conversation_token: null,
    });
    await vi.waitFor(() =>
      expect(document.getElementById("wx-messages")).toHaveTextContent("Fresh answer")
    );
    expect(localStorage.getItem(storageKey)).toBe("51");
    expect(localStorage.getItem(`${storageKey}_token`)).toBe("fresh-token");
  });

  it("restores the chat and drops an expired live conversation after re-verification", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    // The stored conversation token is expired: the socket-ticket endpoint
    // keeps returning 401 even after the widget token is refreshed.
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ detail: "Invalid or expired conversation session." }),
        { status: 401, headers: { "content-type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "999");
    localStorage.setItem(`${storageKey}_token`, "expired-conversation-token");
    localStorage.setItem(`${storageKey}_visitor_count`, "3");

    const widget = await import("./app");
    const sessionMessage = (token: string) =>
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token,
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      });

    const postMessage = vi.spyOn(window, "postMessage");
    widget.handleParentMessage(sessionMessage("signed-session"));

    // The auto live-connect gets 401 and asks the loader for a fresh session.
    await vi.waitFor(() =>
      expect(postMessage).toHaveBeenCalledWith({ type: "wx-refresh" }, location.origin)
    );
    // The loader answers with wx-verify: verification takes over the UI and
    // must not leave the "Talk to a person" bar floating underneath.
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: { type: "wx-verify" },
      })
    );
    const verification = document.getElementById("wx-verification") as HTMLElement;
    const form = document.getElementById("wx-form") as HTMLFormElement;
    const actions = document.getElementById("wx-live-actions") as HTMLDivElement;
    expect(verification.hidden).toBe(false);
    expect(form.hidden).toBe(true);
    expect(actions.hidden).toBe(true);

    // Turnstile re-solves and the fresh session arrives: the chat must come
    // back instead of sticking on "Finishing verification…".
    widget.handleParentMessage(sessionMessage("signed-session-2"));
    await vi.waitFor(() => expect(verification.hidden).toBe(true));
    expect(form.hidden).toBe(false);

    // The retry still 401s, so the dead conversation session is dropped and
    // the visitor can simply chat again on the next open.
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(localStorage.getItem(storageKey)).toBeNull());
    expect(localStorage.getItem(`${storageKey}_token`)).toBeNull();
    expect(localStorage.getItem(`${storageKey}_visitor_count`)).toBeNull();
    await vi.waitFor(() =>
      expect((document.getElementById("wx-talk") as HTMLButtonElement).hidden).toBe(true)
    );
    expect(form.hidden).toBe(false);
  });

  it("coalesces rapid handoff clicks into one ticket, socket, and escalation", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ticket: "live-ticket",
          websocket_path: "/live/conversations/42",
          conversation_id: 42,
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const sockets: MockWebSocket[] = [];
    class MockWebSocket {
      static OPEN = 1;
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      send = vi.fn();

      constructor(_url: string, _protocols: string[]) {
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.();
        });
      }

      close() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "42");
    localStorage.setItem(`${storageKey}_token`, "conversation-token");
    localStorage.setItem(`${storageKey}_visitor_count`, "3");

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    const talk = document.getElementById("wx-talk") as HTMLButtonElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    await vi.waitFor(() => expect(talk.hidden).toBe(false));
    for (let click = 0; click < 5; click += 1) talk.click();

    expect(talk.disabled).toBe(true);
    expect(input.disabled).toBe(true);
    expect(document.getElementById("wx-messages")).toHaveTextContent(
      "Give us a moment while we connect you…",
    );
    await vi.waitFor(() => expect(sockets[0].send).toHaveBeenCalledTimes(1));
    expect(JSON.parse(sockets[0].send.mock.calls[0][0])).toMatchObject({
      version: 1,
      type: "escalate",
    });

    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "state",
        conversation_id: 42,
        mode: "waiting",
        transitioned: true,
      }),
    } as MessageEvent);

    await vi.waitFor(() => expect(talk.disabled).toBe(false));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sockets).toHaveLength(1);
    // The connecting bubble keeps its loader for the whole waiting phase…
    const messages = document.getElementById("wx-messages") as HTMLDivElement;
    expect(messages).toHaveTextContent("Give us a moment while we connect you…");
    expect(messages.querySelector(".wx-live-status .wx-typing")).not.toBeNull();

    // …and resolves in place once an operator accepts.
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "state",
        conversation_id: 42,
        mode: "human",
        transitioned: true,
      }),
    } as MessageEvent);
    expect(messages).toHaveTextContent("You’re now connected to the team.");
    expect(messages).not.toHaveTextContent("Give us a moment while we connect you…");
    expect(messages.querySelector(".wx-live-status .wx-typing")).toBeNull();
  });

  it("resolves the waiting loader into a cancellation notice when the visitor cancels", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          ticket: "live-ticket",
          websocket_path: "/live/conversations/42",
          conversation_id: 42,
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const sockets: MockWebSocket[] = [];
    class MockWebSocket {
      static OPEN = 1;
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      send = vi.fn();

      constructor(_url: string, _protocols: string[]) {
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.();
        });
      }

      close() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "42");
    localStorage.setItem(`${storageKey}_token`, "conversation-token");
    localStorage.setItem(`${storageKey}_visitor_count`, "3");

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    // A reconnect straight into "waiting" (e.g. page reload) shows the same
    // connecting loader as a fresh request.
    await vi.waitFor(() => expect(sockets).toHaveLength(1));
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "state",
        conversation_id: 42,
        mode: "waiting",
      }),
    } as MessageEvent);
    const messages = document.getElementById("wx-messages") as HTMLDivElement;
    expect(messages).toHaveTextContent("Give us a moment while we connect you…");
    expect(messages.querySelector(".wx-live-status .wx-typing")).not.toBeNull();

    const talk = document.getElementById("wx-talk") as HTMLButtonElement;
    expect(document.getElementById("wx-talk-label")).toHaveTextContent("Cancel request");
    talk.click();
    await vi.waitFor(() =>
      expect(
        sockets[0].send.mock.calls
          .map((call) => JSON.parse(call[0] as string))
          .some((event) => event.type === "cancel")
      ).toBe(true)
    );
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "state",
        conversation_id: 42,
        mode: "ai",
      }),
    } as MessageEvent);
    expect(messages).toHaveTextContent("Request cancelled. You’re back with the AI assistant.");
    expect(messages.querySelector(".wx-live-status .wx-typing")).toBeNull();
  });

  it("offers human support only after three visitor messages", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn(async () =>
      new Response(
        [
          `data: ${JSON.stringify({
            type: "conversation",
            conversation_id: 42,
            conversation_token: "conversation-token",
          })}`,
          `data: ${JSON.stringify({ type: "token", content: "Answer" })}`,
          `data: ${JSON.stringify({ type: "done" })}`,
          "",
        ].join("\n\n"),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    const actions = document.getElementById("wx-live-actions") as HTMLDivElement;
    const talk = document.getElementById("wx-talk") as HTMLButtonElement;
    const form = document.getElementById("wx-form") as HTMLFormElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    const send = document.getElementById("wx-send") as HTMLButtonElement;
    expect(actions.hidden).toBe(true);
    expect(talk.hidden).toBe(true);

    for (let messageNumber = 1; messageNumber <= 3; messageNumber += 1) {
      input.value = `Question ${messageNumber}`;
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(messageNumber));
      await vi.waitFor(() => expect(send.disabled).toBe(false));
      expect(actions.hidden).toBe(messageNumber < 3);
    }

    expect(talk.hidden).toBe(false);
    expect(actions).toHaveTextContent("Need more help?");
    expect(actions).toHaveTextContent("Talk to a person");
    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    expect(localStorage.getItem(`${storageKey}_visitor_count`)).toBe("3");
  });

  it("lets a visitor rate the conversation after a few AI messages", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).endsWith("/widget/rating")) {
        return new Response(null, { status: 204 });
      }
      return new Response(
        [
          `data: ${JSON.stringify({
            type: "conversation",
            conversation_id: 42,
            conversation_token: "conversation-token",
          })}`,
          `data: ${JSON.stringify({ type: "token", content: "Answer" })}`,
          `data: ${JSON.stringify({ type: "done" })}`,
          "",
        ].join("\n\n"),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const widget = await import("./app");
    // live escalation OFF - rating must still be offered on a plain AI chat.
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: false,
          },
        },
      })
    );

    const rating = document.getElementById("wx-rating") as HTMLDivElement;
    const form = document.getElementById("wx-form") as HTMLFormElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    const send = document.getElementById("wx-send") as HTMLButtonElement;
    expect(rating.hidden).toBe(true);

    for (let messageNumber = 1; messageNumber <= 3; messageNumber += 1) {
      input.value = `Question ${messageNumber}`;
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(messageNumber));
      await vi.waitFor(() => expect(send.disabled).toBe(false));
    }

    expect(rating.hidden).toBe(false);

    const rateUp = document.getElementById("wx-rate-up") as HTMLButtonElement;
    rateUp.click();

    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) =>
          String(call[0]).endsWith("/widget/rating")
        )
      ).toBe(true)
    );
    const ratingCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).endsWith("/widget/rating")
    )!;
    expect(JSON.parse((ratingCall[1] as RequestInit).body as string)).toMatchObject({
      widget_token: "signed-session",
      conversation_id: 42,
      conversation_token: "conversation-token",
      rating: "up",
    });
    await vi.waitFor(() =>
      expect(document.getElementById("wx-rating-prompt")).toHaveTextContent(
        "Thanks for your feedback."
      )
    );
    expect(rateUp.disabled).toBe(true);
    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    expect(localStorage.getItem(`${storageKey}_rating`)).toBe("up");

    // The thanks lingers briefly, then the rating bar retires for good.
    const actions = document.getElementById("wx-live-actions") as HTMLDivElement;
    await vi.waitFor(() => expect(rating.hidden).toBe(true), { timeout: 4000 });
    expect(actions.hidden).toBe(true);
  });

  it("offers a rating alongside 'Start a new conversation' when closed", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          ticket: "live-ticket",
          websocket_path: "/live/conversations/42",
          conversation_id: 42,
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const sockets: MockWebSocket[] = [];
    class MockWebSocket {
      static OPEN = 1;
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      send = vi.fn();

      constructor(_url: string, _protocols: string[]) {
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.();
        });
      }

      close() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "42");
    localStorage.setItem(`${storageKey}_token`, "conversation-token");

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    await vi.waitFor(() => expect(sockets).toHaveLength(1));
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "state",
        conversation_id: 42,
        mode: "closed",
      }),
    } as MessageEvent);

    const rating = document.getElementById("wx-rating") as HTMLDivElement;
    const newChat = document.getElementById("wx-new-chat") as HTMLButtonElement;
    await vi.waitFor(() => expect(rating.hidden).toBe(false));
    expect(newChat.hidden).toBe(false);
    expect(rating).toHaveTextContent("How was this conversation?");
  });

  it("does not offer the rating again for a previously rated conversation", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    vi.stubGlobal("fetch", vi.fn());

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "42");
    localStorage.setItem(`${storageKey}_token`, "conversation-token");
    localStorage.setItem(`${storageKey}_visitor_count`, "3");
    localStorage.setItem(`${storageKey}_rating`, "up");

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: false,
          },
        },
      })
    );

    const rating = document.getElementById("wx-rating") as HTMLDivElement;
    const actions = document.getElementById("wx-live-actions") as HTMLDivElement;
    expect(rating.hidden).toBe(true);
    expect(actions.hidden).toBe(true);
  });

  it("closes the chat when the stream delivers a moderation close", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const closedText =
      "This conversation has been closed due to repeated inappropriate messages.";
    const fetchMock = vi.fn(async () =>
      new Response(
        [
          `data: ${JSON.stringify({
            type: "conversation",
            conversation_id: 42,
            conversation_token: "conversation-token",
          })}`,
          `data: ${JSON.stringify({ type: "token", content: closedText })}`,
          `data: ${JSON.stringify({
            type: "mode_changed",
            mode: "closed",
            conversation_id: 42,
          })}`,
          "",
        ].join("\n\n"),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    const sockets: unknown[] = [];
    class MockWebSocket {
      static OPEN = 1;
      constructor() {
        sockets.push(this);
      }
      close() {}
      send() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: false,
          },
        },
      })
    );

    const form = document.getElementById("wx-form") as HTMLFormElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    input.value = "abusive message";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() =>
      expect(document.getElementById("wx-messages")).toHaveTextContent(closedText)
    );
    await vi.waitFor(() => expect(form.hidden).toBe(true));
    expect(
      (document.getElementById("wx-new-chat") as HTMLButtonElement).hidden
    ).toBe(false);
    expect(document.getElementById("wx-subtitle")).toHaveTextContent(
      "Conversation closed"
    );
    // A server-side close must not spuriously open a live socket.
    expect(sockets).toHaveLength(0);
    expect(
      fetchMock.mock.calls.some((call) => String(call[0]).includes("/live/"))
    ).toBe(false);
  });

  it("shows the closed notice when sending into an already-closed conversation", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    // The backend's early return carries no token text - just the mode change.
    const fetchMock = vi.fn(async () =>
      new Response(
        [
          `data: ${JSON.stringify({
            type: "mode_changed",
            mode: "closed",
            conversation_id: 42,
          })}`,
          "",
        ].join("\n\n"),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: false,
          },
        },
      })
    );

    const form = document.getElementById("wx-form") as HTMLFormElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    input.value = "hello?";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() =>
      expect(document.getElementById("wx-messages")).toHaveTextContent(
        "This conversation has been closed."
      )
    );
    expect(document.getElementById("wx-messages")).not.toHaveTextContent(
      "(no response)"
    );
    await vi.waitFor(() => expect(form.hidden).toBe(true));
  });

  it("still hands off to the live socket for non-closed mode changes", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).endsWith("/live/visitor/socket-ticket")) {
        return new Response(
          JSON.stringify({
            ticket: "live-ticket",
            websocket_path: "/live/conversations/42",
            conversation_id: 42,
          }),
          { status: 200, headers: { "content-type": "application/json" } }
        );
      }
      return new Response(
        [
          `data: ${JSON.stringify({
            type: "conversation",
            conversation_id: 42,
            conversation_token: "conversation-token",
          })}`,
          `data: ${JSON.stringify({
            type: "mode_changed",
            mode: "waiting",
            conversation_id: 42,
          })}`,
          "",
        ].join("\n\n"),
        { status: 200, headers: { "content-type": "text/event-stream" } }
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const sockets: MockWebSocket[] = [];
    class MockWebSocket {
      static OPEN = 1;
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      send = vi.fn();

      constructor(_url: string, _protocols: string[]) {
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.();
        });
      }

      close() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    const form = document.getElementById("wx-form") as HTMLFormElement;
    const input = document.getElementById("wx-input") as HTMLInputElement;
    input.value = "hello?";
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));

    await vi.waitFor(() => expect(sockets).toHaveLength(1));
    expect(document.getElementById("wx-messages")).not.toHaveTextContent(
      "(no response)"
    );
  });

  it("shows operator typing dots and sends the visitor's own typing signal", async () => {
    window.turnstile = {
      render: vi.fn(() => "widget-id"),
      reset: vi.fn(),
    };
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          ticket: "live-ticket",
          websocket_path: "/live/conversations/42",
          conversation_id: 42,
        }),
        { status: 200, headers: { "content-type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const sockets: MockWebSocket[] = [];
    class MockWebSocket {
      static OPEN = 1;
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      onerror: (() => void) | null = null;
      send = vi.fn();

      constructor(_url: string, _protocols: string[]) {
        sockets.push(this);
        queueMicrotask(() => {
          this.readyState = MockWebSocket.OPEN;
          this.onopen?.();
        });
      }

      close() {}
    }
    vi.stubGlobal("WebSocket", MockWebSocket);

    const storageKey = `wx_conv_17_${encodeURIComponent("https://customer.example")}`;
    localStorage.setItem(storageKey, "42");
    localStorage.setItem(`${storageKey}_token`, "conversation-token");

    const widget = await import("./app");
    widget.handleParentMessage(
      new MessageEvent("message", {
        origin: location.origin,
        source: window,
        data: {
          type: "wx-session",
          session: {
            token: "signed-session",
            installation_id: 17,
            origin: "https://customer.example",
            assistant_name: "Helper",
            business_name: "Acme",
            live_human_escalation_enabled: true,
          },
        },
      })
    );

    await vi.waitFor(() => expect(sockets).toHaveLength(1));
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "state",
        conversation_id: 42,
        mode: "human",
      }),
    } as MessageEvent);

    const messages = document.getElementById("wx-messages") as HTMLDivElement;

    // Operator typing shows the dots; the delivered message replaces them.
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "typing",
        actor_type: "operator",
        typing: true,
      }),
    } as MessageEvent);
    expect(messages.querySelector(".wx-typing")).not.toBeNull();
    sockets[0].onmessage?.({
      data: JSON.stringify({
        version: 1,
        type: "message",
        message: { id: 7, sender_type: "operator", content: "Hello from the team" },
      }),
    } as MessageEvent);
    expect(messages.querySelector(".wx-typing")).toBeNull();
    expect(messages).toHaveTextContent("Hello from the team");

    // Composing sends one throttled typing signal; clearing sends the stop.
    const input = document.getElementById("wx-input") as HTMLInputElement;
    input.value = "typ";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.value = "typing";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    const sent = sockets[0].send.mock.calls
      .map((call) => JSON.parse(call[0] as string))
      .filter((event) => event.type === "typing");
    expect(sent).toEqual([
      { version: 1, type: "typing", typing: true },
      { version: 1, type: "typing", typing: false },
    ]);
  });
});

describe("widget appearance", () => {
  beforeEach(() => {
    vi.resetModules();
    document.body.innerHTML = '<div id="app"></div>';
    document.documentElement.removeAttribute("style");
  });

  function setHash(extra: Record<string, string>) {
    history.replaceState(
      null,
      "",
      `/#${new URLSearchParams({ origin: location.origin, api: "https://api.example", ...extra })}`
    );
  }

  it("shows the Powered by Plug & Play footer by default", async () => {
    setHash({});
    await import("./app");
    const footer = document.getElementById("wx-branding") as HTMLElement;
    expect(footer.hidden).toBe(false);
    expect(footer).toHaveTextContent("Powered by Plug & Play");
  });

  it("hides branding when branding=false", async () => {
    setHash({ branding: "false" });
    await import("./app");
    expect((document.getElementById("wx-branding") as HTMLElement).hidden).toBe(true);
  });

  it("derives readable text color from the accent", async () => {
    setHash({ accent: "#0284c7" }); // dark accent -> white text
    await import("./app");
    expect(document.documentElement.style.getPropertyValue("--accent-contrast")).toBe("#ffffff");
  });

  it("uses dark text on a light accent", async () => {
    setHash({ accent: "#fde047" }); // light yellow -> dark text
    await import("./app");
    expect(document.documentElement.style.getPropertyValue("--accent-contrast")).toBe("#0f172a");
  });
});
