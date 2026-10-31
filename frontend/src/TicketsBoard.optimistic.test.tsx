import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

const TICKET = {
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

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Route reads to canned JSON; the status POST is configurable per test. */
function stubFetch(onStatus: () => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/live/callbacks/1/status") && init?.method === "POST") {
        return onStatus();
      }
      if (/\/sites($|\?|\/)/.test(url)) return json(SITES);
      if (url.includes("/settings")) {
        return json({
          business_name: "Acme Support",
          assistant_name: "Aria",
          custom_instructions: null,
          public_key: "pk_live_test",
          accent_color: "#0284c7",
          launcher_icon: "chat",
          launcher_position: "bottom-right",
          greeting: null,
          launcher_label: null,
          show_branding: true,
          live_human_escalation_enabled: true,
          live_human_escalation_available: true,
        });
      }
      if (url.includes("/live/callbacks")) return json([TICKET]);
      if (url.includes("/live/operators")) {
        return json([{ user_id: "owner-1", email: "owner@acme.com", is_owner: true }]);
      }
      if (url.includes("/conversations")) return json([]);
      if (url.includes("/analytics")) {
        return json({ total_conversations: 0, last_7_days: 0, ratings: {}, unanswered: [] });
      }
      return json({});
    }),
  );
}

async function openBoard() {
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </SWRConfig>,
  );
  await userEvent.click(await screen.findByRole("button", { name: /tickets/i }));
  return within(await screen.findByRole("region", { name: "New" }));
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Tickets board optimistic moves", () => {
  it("moves the card to its new column before the request resolves", async () => {
    // The POST hangs forever - the card must move on optimism alone.
    stubFetch(() => new Promise<Response>(() => {}));
    const newColumn = await openBoard();

    await userEvent.click(newColumn.getByRole("button", { name: "Start" }));

    const inProgress = screen.getByRole("region", { name: "In progress" });
    expect(await within(inProgress).findByText("Vis Itor")).toBeInTheDocument();
    expect(newColumn.queryByText("Vis Itor")).not.toBeInTheDocument();
  });

  it("rolls the card back and shows a toast when the move fails", async () => {
    stubFetch(() => Promise.resolve(json({ detail: "nope" }, 500)));
    const newColumn = await openBoard();

    await userEvent.click(newColumn.getByRole("button", { name: "Start" }));

    expect(await screen.findByText(/couldn't move the ticket/i)).toBeInTheDocument();
    expect(newColumn.getByText("Vis Itor")).toBeInTheDocument();
  });
});
