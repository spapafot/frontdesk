import { cleanup, render, screen, within } from "@testing-library/react";
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
    expect(await screen.findByText("Chat & history")).toBeInTheDocument();
    expect(await screen.findByText(/knowledge/i)).toBeInTheDocument();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
    expect(screen.getByText(/widget guide/i)).toBeInTheDocument();
    expect(screen.queryByText(/^voice$/i)).not.toBeInTheDocument();
    // Tickets only exist for live-support sites; SETTINGS keeps it disabled.
    expect(screen.queryByText(/^tickets$/i)).not.toBeInTheDocument();
  });

  it("surfaces pending tickets in the sidebar and works them across the board", async () => {
    const pendingTicket = {
      id: 1,
      conversation_id: 11,
      customer_name: "Vis Itor",
      customer_email: "vis@example.com",
      customer_message: "Please call me back.",
      status: "pending",
      assignee_user_id: null,
      archived: false,
      created_at: "2026-07-14T08:00:00Z",
      resolved_at: null,
    };
    const resolvedTicket = {
      ...pendingTicket,
      id: 2,
      customer_name: null,
      customer_email: "old@example.com",
      customer_message: null,
      status: "resolved",
      resolved_at: "2026-07-13T10:00:00Z",
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      let body: unknown = {};
      if (/\/sites($|\?|\/)/.test(url)) body = SITES;
      else if (url.includes("/settings")) body = {
        ...SETTINGS,
        live_human_escalation_enabled: true,
        live_human_escalation_available: true,
      };
      // The status POST must match before the callbacks list.
      else if (url.includes("/live/callbacks/1/status") && init?.method === "POST") {
        const requested = JSON.parse(String(init.body)) as { status: string };
        body = {
          ...pendingTicket,
          status: requested.status,
          resolved_at: requested.status === "resolved" ? "2026-07-14T09:00:00Z" : null,
        };
      }
      else if (url.includes("/live/callbacks")) body = [pendingTicket, resolvedTicket];
      else if (url.includes("/live/operators")) {
        body = [{ user_id: "owner-1", email: "owner@acme.com", is_owner: true }];
      }
      else if (url.includes("/conversations")) body = [];
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
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    // The nav item carries the pending count as an amber badge.
    const ticketsNav = await screen.findByRole("button", { name: /tickets/i });
    expect(ticketsNav.textContent).toContain("1");
    await userEvent.click(ticketsNav);

    // The board renders the three columns with the ticket under "New".
    const newColumn = await screen.findByRole("region", { name: "New" });
    expect(within(newColumn).getByText("Vis Itor")).toBeInTheDocument();
    expect(within(newColumn).getByText("vis@example.com")).toBeInTheDocument();
    expect(within(newColumn).getByText("Please call me back.")).toBeInTheDocument();
    const resolvedColumn = screen.getByRole("region", { name: "Resolved" });
    // A nameless ticket shows its email as the card title and in the email row.
    expect(within(resolvedColumn).getAllByText("old@example.com").length).toBeGreaterThan(0);

    // Start moves the card to In progress, then Resolve completes it.
    await userEvent.click(within(newColumn).getByRole("button", { name: "Start" }));
    const inProgressColumn = screen.getByRole("region", { name: "In progress" });
    expect(await within(inProgressColumn).findByText("Vis Itor")).toBeInTheDocument();
    await userEvent.click(within(inProgressColumn).getByRole("button", { name: "Resolve" }));
    expect(await within(resolvedColumn).findByText("Vis Itor")).toBeInTheDocument();

    const statusCalls = fetchMock.mock.calls.filter(([input]) =>
      String(input).includes("/live/callbacks/1/status"),
    );
    expect(statusCalls.map(([, init]) => JSON.parse(String((init as RequestInit).body)))).toEqual([
      { status: "in_progress" },
      { status: "resolved" },
    ]);
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
    await userEvent.click(screen.getByRole("button", { name: "Chat & history" }));
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

  it("makes a visitor's AI conversation read-only in history but keeps the test chat editable", async () => {
    const visitor = {
      id: 31,
      title: "Visitor question",
      started_at: "2026-07-14T08:00:00Z",
      rating: null,
      summary: null,
      mode: "ai",
      assigned_user_id: null,
      escalation_requested_at: null,
      accepted_at: null,
      closed_at: null,
      last_message_at: "2026-07-14T08:05:00Z",
      is_visitor: true,
    };
    // The admin's own test chat is also an AI conversation, but has no visitor
    // session, so it must stay editable.
    const testChat = { ...visitor, id: 32, title: "My test chat", is_visitor: false };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      let body: unknown = {};
      if (/\/sites($|\?|\/)/.test(url)) body = SITES;
      else if (url.includes("/settings")) body = SETTINGS;
      else if (url.includes("/messages")) body = [
        { id: 1, role: "user", content: "How much does it cost?", sender_type: "visitor", sender_display_name: null, created_at: "2026-07-14T08:01:00Z" },
        { id: 2, role: "assistant", content: "We are still in beta.", sender_type: "ai", sender_display_name: null, created_at: "2026-07-14T08:02:00Z" },
      ];
      else if (url.includes("/conversations")) body = [visitor, testChat];
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

    // The visitor conversation renders as a read-only transcript with no composer.
    await userEvent.click(await screen.findByText("Visitor question"));
    expect(await screen.findByText("We are still in beta.")).toBeInTheDocument();
    expect(screen.getByText(/read-only record/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Ask a question...")).not.toBeInTheDocument();

    // The admin's own test chat keeps its composer.
    await userEvent.click(screen.getByText("My test chat"));
    expect(await screen.findByPlaceholderText("Ask a question...")).toBeInTheDocument();
    expect(screen.queryByText(/read-only record/i)).not.toBeInTheDocument();
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
    expect(
      await screen.findByText(/0 messages from this site this month/)
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Billing page" })).toBeInTheDocument();
  });

  it("hides owner-only navigation for team members", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        let body: unknown = {};
        if (/\/sites($|\?|\/)/.test(url)) {
          body = [{ ...SITES[0], role: "member" }];
        } else if (url.includes("/settings")) body = SETTINGS;
        else if (url.includes("/conversations")) body = [];
        else if (url.includes("/analytics")) {
          body = { total_conversations: 0, last_7_days: 0, ratings: {}, unanswered: [] };
        }
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      })
    );
    renderApp();

    // Members keep the working views but never see Settings.
    expect(await screen.findByText(/knowledge/i)).toBeInTheDocument();
    expect(screen.getByText("Chat & history")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Settings" })
    ).not.toBeInTheDocument();

    // The account page is user-level: members reach it (no bounce to history).
    await userEvent.click(screen.getByRole("button", { name: /account settings/i }));
    expect(
      await screen.findByRole("heading", { name: /^account$/i })
    ).toBeInTheDocument();
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
