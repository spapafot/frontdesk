import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import App from "./App";

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
    expect(await screen.findByText("Chat & history")).toBeInTheDocument();
    expect(await screen.findByText(/knowledge/i)).toBeInTheDocument();
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
    expect(screen.getByText(/widget guide/i)).toBeInTheDocument();
    expect(screen.queryByText(/^voice$/i)).not.toBeInTheDocument();
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
