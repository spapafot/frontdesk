import { cleanup, render, screen } from "@testing-library/react";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import App from "./App";

const SETTINGS = {
  business_name: "Acme Support",
  assistant_name: "Aria",
  custom_instructions: null,
  public_key: "pk_live_test",
};

// Route each API call to canned JSON so the whole app shell can mount without
// a backend. This is an integration render: SWR fetchers -> fetch -> UI.
function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown = {};
    if (url.includes("/settings")) body = SETTINGS;
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
      <App />
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
    expect(screen.queryByText(/^voice$/i)).not.toBeInTheDocument();
  });

  it("renders settings when optional widget usage values are missing", async () => {
    renderApp();
    await userEvent.click(await screen.findByRole("button", { name: "Settings" }));
    expect(await screen.findByText("0 of 0 messages used this month")).toBeInTheDocument();
  });
});
