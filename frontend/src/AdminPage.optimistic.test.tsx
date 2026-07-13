import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPage } from "./pages/AdminPage";
import { SiteProvider } from "./components/SiteProvider";
import { ToastProvider } from "./components/Toast";

const SITE = {
  id: 1,
  name: "Acme",
  assistant_name: "Aria",
  type: "general",
  public_key: "pk_test",
  widget_origin: null,
  widget_enabled: true,
  widget_monthly_limit: 0,
  widget_monthly_usage: 0,
  created_at: "2026-01-01T00:00:00Z",
};

const DOC = {
  id: 1,
  title: "Handbook",
  type: "pdf",
  is_active: true,
  processing_status: "ready",
  chunk_count: 3,
  created_at: "2026-01-01T00:00:00Z",
  processed_at: null,
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Route reads to canned JSON; the DELETE handler is configurable per test. */
function stubFetch(onDelete: () => Promise<Response>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "DELETE") return onDelete();
      if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
      if (url.includes("/knowledge/documents")) return json([DOC]);
      return json({});
    }),
  );
}

function renderAdmin() {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ToastProvider>
        <SiteProvider>
          <AdminPage />
        </SiteProvider>
      </ToastProvider>
    </SWRConfig>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AdminPage optimistic knowledge-base actions", () => {
  it("removes a document row immediately, before the delete request resolves", async () => {
    // DELETE hangs forever - the row must disappear on optimism alone.
    stubFetch(() => new Promise<Response>(() => {}));
    renderAdmin();

    await screen.findByText("Handbook");
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.queryByText("Handbook")).not.toBeInTheDocument(),
    );
  });

  it("restores the row and shows a toast when the delete request fails", async () => {
    stubFetch(() => Promise.resolve(json({ detail: "nope" }, 500)));
    renderAdmin();

    await screen.findByText("Handbook");
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    // Toast surfaces the failure and the optimistic removal rolls back.
    expect(await screen.findByText(/couldn't delete/i)).toBeInTheDocument();
    expect(screen.getByText("Handbook")).toBeInTheDocument();
  });

  it("shows a loading skeleton while documents are still loading", async () => {
    // Documents GET never resolves so isLoading stays true.
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        if (url.includes("/knowledge/documents"))
          return new Promise<Response>(() => {});
        return json({});
      }),
    );
    renderAdmin();

    expect(
      await screen.findByRole("status", { name: /loading documents/i }),
    ).toBeInTheDocument();
  });
});
