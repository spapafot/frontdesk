import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import useSWR from "swr";
import { analyticsKey, getAnalytics } from "./api/analytics";
import {
  conversationsKey,
  deleteConversation,
  listConversations,
  rateConversation,
  Rating,
  renameConversation,
} from "./api/conversations";
import { Sidebar, View } from "./components/Sidebar";
import { SiteProvider, useSite } from "./components/SiteProvider";
import { ToastProvider, useToast } from "./components/Toast";
import { AdminPage } from "./pages/AdminPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ChatPage } from "./pages/ChatPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WidgetDocsPage } from "./pages/WidgetDocsPage";

// Each view is a real URL so refresh restores it and the browser Back/Forward
// buttons move between views instead of leaving the app.
const VIEW_PATHS: Record<View, string> = {
  chat: "/",
  analytics: "/analytics",
  admin: "/knowledge",
  settings: "/settings",
  widgetDocs: "/widget-guide",
};

function viewFromPath(pathname: string): View {
  if (pathname.startsWith("/analytics")) return "analytics";
  if (pathname.startsWith("/knowledge")) return "admin";
  if (pathname.startsWith("/settings")) return "settings";
  if (pathname.startsWith("/widget-guide")) return "widgetDocs";
  return "chat";
}

export default function App() {
  return (
    <ToastProvider>
      <SiteProvider>
        <AppShell />
      </SiteProvider>
    </ToastProvider>
  );
}

function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const view = viewFromPath(location.pathname);
  const { sites, selectedSiteId, current, isLoading, createSite } = useSite();
  const { showToast } = useToast();
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(
    null
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Collapse the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Conversations belong to one site; drop any selection when the site changes.
  useEffect(() => {
    setSelectedConversationId(null);
  }, [selectedSiteId]);

  const { data: conversations, mutate: mutateConversations } = useSWR(
    selectedSiteId != null ? conversationsKey(selectedSiteId) : null,
    () => listConversations(selectedSiteId as number)
  );
  const { mutate: mutateAnalytics } = useSWR(
    selectedSiteId != null ? analyticsKey(selectedSiteId) : null,
    () => getAnalytics(selectedSiteId as number)
  );

  const selectedConversation = conversations?.find(
    (c) => c.id === selectedConversationId
  );

  // If the selected conversation no longer exists, clear the selection.
  useEffect(() => {
    if (
      selectedConversationId !== null &&
      conversations &&
      !conversations.some((c) => c.id === selectedConversationId)
    ) {
      setSelectedConversationId(null);
    }
  }, [conversations, selectedConversationId]);

  const onNewChat = () => {
    setSelectedConversationId(null);
    setSidebarOpen(false);
    navigate("/");
  };

  const onSelectConversation = (id: number) => {
    setSelectedConversationId(id);
    setSidebarOpen(false);
    navigate("/");
  };

  const onConversationCreated = (id: number) => {
    // Optimistically insert the new conversation FIRST so the "stale selection"
    // guard below never bounces us back to a new chat before the list revalidates.
    mutateConversations(
      (prev) =>
        prev && !prev.some((c) => c.id === id)
          ? [
              {
                id,
                title: null,
                started_at: new Date().toISOString(),
                rating: null,
                summary: null,
              },
              ...prev,
            ]
          : prev,
      { revalidate: true }
    );
    setSelectedConversationId(id);
  };

  const onRenameConversation = async (id: number, title: string) => {
    if (selectedSiteId == null) return;
    try {
      await mutateConversations(
        async (list) => {
          const updated = await renameConversation(selectedSiteId, id, title);
          return list?.map((c) => (c.id === updated.id ? updated : c)) ?? [];
        },
        {
          optimisticData: (list) =>
            list?.map((c) => (c.id === id ? { ...c, title } : c)) ?? [],
          rollbackOnError: true,
          revalidate: false,
        }
      );
    } catch {
      showToast("Couldn't rename the conversation. Restored.");
    }
  };

  const onDeleteConversation = async (id: number) => {
    if (selectedSiteId == null) return;
    if (id === selectedConversationId) setSelectedConversationId(null);
    try {
      await mutateConversations(
        async (list) => {
          await deleteConversation(selectedSiteId, id);
          return list?.filter((c) => c.id !== id) ?? [];
        },
        {
          optimisticData: (list) => list?.filter((c) => c.id !== id) ?? [],
          rollbackOnError: true,
          revalidate: false,
        }
      );
      mutateAnalytics();
    } catch {
      showToast("Couldn't delete the conversation. Restored.");
    }
  };

  const onRate = async (id: number, rating: Rating) => {
    if (selectedSiteId == null) return;
    try {
      await mutateConversations(
        async (list) => {
          const updated = await rateConversation(selectedSiteId, id, rating);
          return list?.map((c) => (c.id === updated.id ? updated : c)) ?? [];
        },
        {
          optimisticData: (list) =>
            list?.map((c) => (c.id === id ? { ...c, rating } : c)) ?? [],
          rollbackOnError: true,
          revalidate: false,
        }
      );
      mutateAnalytics();
    } catch {
      showToast("Couldn't save your rating. Restored.");
    }
  };

  const onOpenConversation = (id: number) => {
    setSelectedConversationId(id);
    navigate("/");
  };

  if (!isLoading && sites && sites.length === 0) {
    return <FirstRunPanel onCreate={createSite} />;
  }

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        view={view}
        businessName={current?.name}
        assistantName={current?.assistant_name}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={onNewChat}
        onSelectConversation={onSelectConversation}
        onNavigate={(next) => navigate(VIEW_PATHS[next])}
        onRenameConversation={onRenameConversation}
        onDeleteConversation={onDeleteConversation}
      />

      {/* Scrim behind the mobile drawer. */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
          onClick={() => setSidebarOpen(false)}
          role="presentation"
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar with the menu toggle. */}
        <header className="flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
          >
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
              <path
                d="M4 6h14M4 11h14M4 16h14"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
          <span className="truncate text-sm font-semibold text-slate-800">
            {current?.assistant_name ?? "Plug & Play"}
          </span>
        </header>

        <main className="min-h-0 min-w-0 flex-1">
        <Routes>
          <Route
            path="/"
            element={
              <ChatPage
                selectedConversationId={selectedConversationId}
                rating={selectedConversation?.rating ?? null}
                onConversationCreated={onConversationCreated}
                onRate={onRate}
              />
            }
          />
          <Route path="/knowledge" element={<AdminPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/widget-guide" element={<WidgetDocsPage />} />
          <Route
            path="/analytics"
            element={<AnalyticsPage onOpenConversation={onOpenConversation} />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </main>
      </div>
    </div>
  );
}

function FirstRunPanel({
  onCreate,
}: {
  onCreate: (name: string, url: string) => Promise<unknown>;
}) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onCreate(trimmed, url.trim());
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full items-center justify-center bg-slate-50 p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div className="text-center">
          <h1 className="text-lg font-semibold text-slate-900">Add your first website</h1>
          <p className="mt-1 text-sm text-slate-500">
            Each website gets its own assistant, knowledge base, and widget.
          </p>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          Website name
          <input
            type="text"
            autoFocus
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Acme Store"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
        </label>

        <div>
          <label className="block text-sm font-medium text-slate-700">
            Website URL <span className="font-normal text-slate-400">(optional)</span>
            <input
              type="url"
              maxLength={255}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
          </label>
          <p className="mt-1 text-xs text-slate-400">
            The exact origin where the widget runs. You can set or change this later in Settings.
          </p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          {busy ? "Creating…" : "Create website"}
        </button>
      </form>
    </div>
  );
}
