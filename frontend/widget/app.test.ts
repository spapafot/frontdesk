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
    expect(document.getElementById("wx-messages")).toHaveTextContent(
      "Looking for someone from the team…",
    );
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

  it("marks a previously rated conversation as already rated", async () => {
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
    const rateUp = document.getElementById("wx-rate-up") as HTMLButtonElement;
    const rateDown = document.getElementById("wx-rate-down") as HTMLButtonElement;
    expect(rating.hidden).toBe(false);
    expect(document.getElementById("wx-rating-prompt")).toHaveTextContent(
      "Thanks for your feedback."
    );
    expect(rateUp).toHaveClass("selected");
    expect(rateUp.disabled).toBe(true);
    expect(rateDown.disabled).toBe(true);
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
