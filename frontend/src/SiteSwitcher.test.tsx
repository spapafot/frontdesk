import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import App from "./App";

const BASE_SETTINGS = {
  business_name: "Acme Support",
  assistant_name: "Aria",
  custom_instructions: null,
  public_key: "pk_live_1",
  accent_color: "#0284c7",
  launcher_icon: "chat",
  launcher_position: "bottom-right",
  greeting: "Hi!",
  launcher_label: null,
  show_branding: true,
};

const TWO_SITES = [
  {
    id: 1,
    name: "Acme Support",
    assistant_name: "Aria",
    type: "general",
    public_key: "pk_live_1",
    widget_origin: null,
    widget_enabled: true,
    widget_monthly_usage: 0,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Beta Site",
    assistant_name: "Bo",
    type: "general",
    public_key: "pk_live_2",
    widget_origin: null,
    widget_enabled: true,
    widget_monthly_usage: 0,
    created_at: "2026-01-02T00:00:00Z",
  },
];

// Settings vary by ?site_id=, so the assistant name proves which site the app
// is scoped to after a switch - i.e. that SWR keys don't collide across sites.
function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    let body: unknown = {};
    if (/\/sites($|\?|\/)/.test(url)) body = TWO_SITES;
    else if (url.includes("/settings")) {
      const id = Number(url.match(/site_id=(\d+)/)?.[1] ?? 0);
      body =
        id === 2
          ? {
              ...BASE_SETTINGS,
              assistant_name: "Bo",
              business_name: "Beta Site",
            }
          : BASE_SETTINGS;
    } else if (url.includes("/conversations")) body = [];
    else if (url.includes("/analytics")) {
      body = {
        total_conversations: 0,
        last_7_days: 0,
        ratings: {},
        unanswered: [],
      };
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
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </SWRConfig>,
  );
}

describe("Site switcher", () => {
  it("switches the whole app to another site's data", async () => {
    renderApp();
    // Defaults to the first site.
    expect(await screen.findAllByText("Aria")).not.toHaveLength(0);

    await userEvent.click(screen.getByLabelText("Select website"));
    const menu = await screen.findByRole("button", { name: "Beta Site" });
    await userEvent.click(menu);

    // The chat header + sidebar now reflect site 2's settings.
    expect(await screen.findAllByText("Bo")).not.toHaveLength(0);
  });

  it("opens a dialog with name and URL fields when adding a website", async () => {
    renderApp();
    await userEvent.click(await screen.findByLabelText("Select website"));
    await userEvent.click(screen.getByRole("button", { name: /add website/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/website name/i)).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/website url/i)).toBeInTheDocument();
  });

  it("opens a rename dialog prefilled with the site name from Settings", async () => {
    renderApp();
    await userEvent.click(
      await screen.findByRole("button", { name: "Settings" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /rename website/i }),
    );

    const dialog = await screen.findByRole("dialog");
    const input = within(dialog).getByLabelText(
      /website name/i,
    ) as HTMLInputElement;
    expect(input.value).toBe("Acme Support");
  });

  it("confirms before deleting a website from Settings", async () => {
    renderApp();
    await userEvent.click(
      await screen.findByRole("button", { name: "Settings" }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: /delete website/i }),
    );

    expect(
      await screen.findByRole("heading", { name: /delete website/i }),
    ).toBeInTheDocument();
  });
});
