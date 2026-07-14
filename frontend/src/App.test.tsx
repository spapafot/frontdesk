import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import App from "./App";

vi.mock("./hooks/useLiveSupport", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./hooks/useLiveSupport")>()),
  useLiveInbox: () => ({
    online: false,
    connected: true,
    waiting: [],
    error: null,
    setOnline: vi.fn(),
    clearWaiting: vi.fn(),
  }),
}));

const SETTINGS = {
  business_name: "Acme Support",
  assistant_name: "Aria",
  custom_instructions: null,
  public_key: "pk_live_test",
  accent_color: "#0284c7",
  launcher_icon: "chat",
  launcher_position: "bottom-right",
  greeting: "Hi! How can I help you today?",
  launcher_label: null,
  show_branding: true,
  live_human_escalation_enabled: false,
  live_human_escalation_available: false,
};

const SITES = [
  {
    id: 1,
    name: "Acme Support",
    assistant_name: "Aria",
    type: "general",
    public_key: "pk_live_test",
    widget_origin: null,
    widget_enabled: true,
    widget_monthly_limit: 0,
    widget_monthly_usage: 0,
    created_at: "2026-01-01T00:00:00Z",
  },
];

// Route each API call to canned JSON so the whole app shell can mount without
// a backend. This is an integration render: SWR fetchers -> fetch -> UI. The
// site list is matched FIRST because every other admin URL now carries a
// ?site_id= query the shell adds once a site is selected.
function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown = {};
    if (/\/sites($|\?|\/)/.test(url)) body = SITES;
    else if (url.includes("/settings")) body = SETTINGS;
    else if (url.includes("/conversations")) body = [];
    else if (url.includes("/analytics")) {
      body = { total_conversations: 0, last_7_days: 0, ratings: {}, unanswered: [] };
    }
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", mockFetch());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderApp() {
  // Isolate SWR cache per test so state doesn't leak between renders.
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </SWRConfig>
  );
}

describe("App shell", () => {
  it("mounts the chat view and renders the assistant name from settings", async () => {
    renderApp();
    // assistant_name is shown in the sidebar and the chat header.
    const matches = await screen.findAllByText("Aria");
    expect(matches.length).toBeGreaterThan(0);
  });

  it("renders navigation to the admin views", async () => {
    renderApp();
    expect(await screen.findByText(/knowledge/i)).toBeInTheDocument();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
    expect(screen.getByText(/widget guide/i)).toBeInTheDocument();
    expect(screen.queryByText(/^voice$/i)).not.toBeInTheDocument();
  });

  it("defaults to Live support when enabled and separates active work from history", async () => {
    const waiting = {
      id: 11,
      title: "Waiting request",
      started_at: "2026-07-14T08:00:00Z",
      rating: null,
      summary: null,
      mode: "waiting",
      assigned_user_id: null,
      escalation_requested_at: "2026-07-14T08:01:00Z",
      accepted_at: null,
      closed_at: null,
      last_message_at: "2026-07-14T08:01:00Z",
    };
    const closed = {
      ...waiting,
      id: 12,
      title: "Closed request",
      mode: "closed",
      closed_at: "2026-07-14T08:02:00Z",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      let body: unknown = {};
      if (/\/sites($|\?|\/)/.test(url)) body = SITES;
      else if (url.includes("/settings")) body = {
        ...SETTINGS,
        live_human_escalation_enabled: true,
        live_human_escalation_available: true,
      };
      else if (url.includes("/conversations")) body = [waiting, closed];
      else if (url.includes("/live/callbacks")) body = [];
      else if (url.includes("/analytics")) body = {
        total_conversations: 0,
        last_7_days: 0,
        ratings: {},
        unanswered: [],
      };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }));

    renderApp();

    expect(await screen.findByText("Waiting request")).toBeInTheDocument();
    expect(screen.queryByText("Closed request")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new chat/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Chat history" }));
    expect(await screen.findByText("Closed request")).toBeInTheDocument();
    expect(screen.queryByText("Waiting request")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
  });

  it("shows a closed conversation transcript when live support is disabled", async () => {
    const closed = {
      id: 21,
      title: "Closed chat",
      started_at: "2026-07-14T08:00:00Z",
      rating: null,
      summary: null,
      mode: "closed",
      assigned_user_id: null,
      escalation_requested_at: null,
      accepted_at: "2026-07-14T08:01:30Z",
      closed_at: "2026-07-14T08:05:00Z",
      last_message_at: "2026-07-14T08:05:00Z",
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      let body: unknown = {};
      if (/\/sites($|\?|\/)/.test(url)) body = SITES;
      // SETTINGS keeps live support disabled, matching the toggle being off.
      else if (url.includes("/settings")) body = SETTINGS;
      // Match the transcript endpoint before the conversations list.
      else if (url.includes("/messages")) body = [
        { id: 1, role: "user", content: "I need a human", sender_type: "visitor", sender_display_name: null, created_at: "2026-07-14T08:01:00Z" },
        { id: 2, role: "assistant", content: "Hi, this is Sam from support", sender_type: "operator", sender_display_name: "Sam", created_at: "2026-07-14T08:02:00Z" },
      ];
      else if (url.includes("/conversations")) body = [closed];
      else if (url.includes("/analytics")) body = {
        total_conversations: 0,
        last_7_days: 0,
        ratings: {},
        unanswered: [],
      };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }));

    renderApp();

    await userEvent.click(await screen.findByText("Closed chat"));
    // The stored transcript renders (operator name + both messages) rather than
    // hanging on the live-conversation loading skeleton.
    expect(await screen.findByText("Hi, this is Sam from support")).toBeInTheDocument();
    expect(screen.getByText("I need a human")).toBeInTheDocument();
    expect(screen.getByText("Sam")).toBeInTheDocument();
    expect(screen.getByText("Conversation ended")).toBeInTheDocument();
  });

  it("shows widget installation documentation and supported attributes", async () => {
    renderApp();
    await userEvent.click(await screen.findByRole("button", { name: "Widget guide" }));
    expect(await screen.findByRole("heading", { name: /add the chat widget/i })).toBeInTheDocument();
    expect(screen.getByText("data-site-key")).toBeInTheDocument();
    expect(screen.getByText("data-greeting")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /install on wordpress/i })).toBeInTheDocument();
  });

  it("renders settings when optional widget usage values are missing", async () => {
    renderApp();
    await userEvent.click(await screen.findByRole("button", { name: "Settings" }));
    expect(await screen.findByText("0 of 0 messages used this month")).toBeInTheDocument();
  });

  it("shows a first-run panel with name and URL fields when there are no sites", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const body = /\/sites($|\?|\/)/.test(url) ? [] : {};
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      })
    );
    renderApp();
    expect(
      await screen.findByRole("heading", { name: /add your first website/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/website name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/website url/i)).toBeInTheDocument();
  });
});
