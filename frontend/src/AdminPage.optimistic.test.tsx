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
  source_url: null,
  is_active: true,
  processing_status: "ready",
  chunk_count: 3,
  created_at: "2026-01-01T00:00:00Z",
  processed_at: null,
};

const URL_DOC = {
  ...DOC,
  id: 2,
  title: "Pricing",
  type: "url",
  source_url: "https://acme.com/pricing",
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

  it("gates link ingestion behind the responsibility disclaimer", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push({ url, init });
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        if (url.includes("/knowledge/links")) return json(URL_DOC, 202);
        if (url.includes("/knowledge/documents")) return json([]);
        return json({});
      }),
    );
    renderAdmin();

    const input = await screen.findByPlaceholderText(/example\.com/i);
    await userEvent.type(input, "https://acme.com/pricing");
    await userEvent.click(screen.getByRole("button", { name: "Add link" }));

    // The disclaimer opens and nothing is posted until it is acknowledged.
    const confirm = await screen.findByRole("button", { name: /add page/i });
    expect(confirm).toBeDisabled();
    expect(calls.some((c) => c.url.includes("/knowledge/links"))).toBe(false);

    await userEvent.click(screen.getByRole("checkbox"));
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    await waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.url.includes("/knowledge/links") && c.init?.method === "POST",
        ),
      ).toBe(true),
    );
    const linkCall = calls.find((c) => c.url.includes("/knowledge/links"));
    expect(JSON.parse(String(linkCall?.init?.body))).toEqual({
      url: "https://acme.com/pricing",
    });
    expect(await screen.findByText(/reading that page/i)).toBeInTheDocument();
  });

  it("rescans a link document on click", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push({ url, init });
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        if (url.includes("/rescan"))
          return json({ ...URL_DOC, processing_status: "queued" }, 202);
        if (url.includes("/knowledge/documents")) return json([URL_DOC]);
        return json({});
      }),
    );
    renderAdmin();

    await screen.findByText("Pricing");
    await userEvent.click(screen.getByRole("button", { name: "Rescan" }));

    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.url.includes("/rescan") && c.init?.method === "POST",
        ),
      ).toBe(true),
    );
    // The row flips to queued optimistically.
    expect(await screen.findByText("Queued")).toBeInTheDocument();
  });

  it("previews the stored chunks for a document", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        // Must precede the /knowledge/documents check - the chunks URL contains both.
        if (url.includes("/chunks"))
          return json([
            { id: 10, content: "First chunk text" },
            { id: 11, content: "Second chunk text" },
          ]);
        if (url.includes("/knowledge/documents")) return json([DOC]);
        return json({});
      }),
    );
    renderAdmin();

    await screen.findByText("Handbook");
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("First chunk text")).toBeInTheDocument();
    expect(screen.getByText("Second chunk text")).toBeInTheDocument();
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

const FAQ_DOC = {
  ...DOC,
  id: 3,
  title: "What are your opening hours?",
  type: "faq",
  chunk_count: 1,
  content: "We are open 9-5, Monday to Friday.",
};

describe("AdminPage FAQ entries", () => {
  it("lists FAQs in their own section with Edit but no Rescan", async () => {
    stubFetchDocs([DOC, FAQ_DOC]);
    renderAdmin();

    // Rendered exactly once: the Documents filter must exclude type "faq".
    await screen.findByText(FAQ_DOC.title);
    expect(screen.getAllByText(FAQ_DOC.title)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Rescan" })).not.toBeInTheDocument();
  });

  it("adds an FAQ via the dialog and renders the saved row without refetching", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push({ url, init });
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        if (url.includes("/knowledge/faqs")) return json(FAQ_DOC, 201);
        if (url.includes("/knowledge/documents")) return json([]);
        return json({});
      }),
    );
    renderAdmin();

    await userEvent.click(
      await screen.findByRole("button", { name: "Add FAQ" }),
    );
    await userEvent.type(
      screen.getByLabelText(/question/i),
      FAQ_DOC.title,
    );
    await userEvent.type(screen.getByLabelText(/answer/i), FAQ_DOC.content);
    await userEvent.click(screen.getByRole("button", { name: "Save FAQ" }));

    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.url.includes("/knowledge/faqs") && c.init?.method === "POST",
        ),
      ).toBe(true),
    );
    const faqCall = calls.find((c) => c.url.includes("/knowledge/faqs"));
    expect(JSON.parse(String(faqCall?.init?.body))).toEqual({
      question: FAQ_DOC.title,
      answer: FAQ_DOC.content,
    });
    // The row comes straight from the response via the cache patch.
    expect(await screen.findByText(FAQ_DOC.title)).toBeInTheDocument();
  });

  it("prefills the dialog when editing and saves via PUT", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const updated = { ...FAQ_DOC, content: "We are open 24/7 now." };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push({ url, init });
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        if (url.includes(`/knowledge/faqs/${FAQ_DOC.id}`)) return json(updated);
        if (url.includes("/knowledge/documents")) return json([FAQ_DOC]);
        return json({});
      }),
    );
    renderAdmin();

    await screen.findByText(FAQ_DOC.title);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(screen.getByLabelText(/question/i)).toHaveValue(FAQ_DOC.title);
    expect(screen.getByLabelText(/answer/i)).toHaveValue(FAQ_DOC.content);

    await userEvent.clear(screen.getByLabelText(/answer/i));
    await userEvent.type(screen.getByLabelText(/answer/i), updated.content);
    await userEvent.click(screen.getByRole("button", { name: "Save FAQ" }));

    await waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.url.includes(`/knowledge/faqs/${FAQ_DOC.id}`) &&
            c.init?.method === "PUT",
        ),
      ).toBe(true),
    );
    const putCall = calls.find((c) => c.init?.method === "PUT");
    expect(JSON.parse(String(putCall?.init?.body))).toEqual({
      question: FAQ_DOC.title,
      answer: updated.content,
    });
    // Dialog closes after a successful save.
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Save FAQ" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("keeps the dialog open and surfaces the server error detail on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        if (url.includes("/knowledge/faqs"))
          return json(
            { detail: "Could not index the FAQ entry. Please try again." },
            502,
          );
        if (url.includes("/knowledge/documents")) return json([]);
        return json({});
      }),
    );
    renderAdmin();

    await userEvent.click(
      await screen.findByRole("button", { name: "Add FAQ" }),
    );
    await userEvent.type(screen.getByLabelText(/question/i), FAQ_DOC.title);
    await userEvent.type(screen.getByLabelText(/answer/i), FAQ_DOC.content);
    await userEvent.click(screen.getByRole("button", { name: "Save FAQ" }));

    expect(
      await screen.findByText(/could not index the faq entry/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save FAQ" })).toBeInTheDocument();
  });

  it("previews the stored chunks for an FAQ entry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
        // Must precede the /knowledge/documents check - the chunks URL contains both.
        if (url.includes("/chunks"))
          return json([
            {
              id: 20,
              content: `${FAQ_DOC.title}\n\n${FAQ_DOC.content}`,
            },
          ]);
        if (url.includes("/knowledge/documents")) return json([FAQ_DOC]);
        return json({});
      }),
    );
    renderAdmin();

    await screen.findByText(FAQ_DOC.title);
    await userEvent.click(screen.getByRole("button", { name: "Preview" }));

    expect(
      await screen.findByText(new RegExp(FAQ_DOC.content)),
    ).toBeInTheDocument();
  });
});

/** Route reads to canned JSON with a fixed documents payload. */
function stubFetchDocs(docs: unknown[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (/\/sites($|\?|\/)/.test(url)) return json([SITE]);
      if (url.includes("/knowledge/documents")) return json(docs);
      return json({});
    }),
  );
}
