import { useCallback, useEffect, useState } from "react";
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
import {
  archiveCallback,
  assignCallback,
  CallbackTicket,
  callbacksKey,
  listCallbacks,
  listOperators,
  LiveState,
  operatorsKey,
  setCallbackStatus,
  TicketStatus,
} from "./api/live";
import { getSettings, settingsKey } from "./api/settings";
import { useAuth } from "./components/AuthGate";
import { Sidebar, View } from "./components/Sidebar";
import { SiteProvider, useSite } from "./components/SiteProvider";
import { ToastProvider, useToast } from "./components/Toast";
import { AdminPage } from "./pages/AdminPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ChatPage } from "./pages/ChatPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TicketsPage } from "./pages/TicketsPage";
import { WidgetDocsPage } from "./pages/WidgetDocsPage";
import { useLiveInbox } from "./hooks/useLiveSupport";

// Each view is a real URL so refresh restores it and the browser Back/Forward
// buttons move between views instead of leaving the app.
const VIEW_PATHS: Record<View, string> = {
  live: "/live",
  history: "/history",
  tickets: "/tickets",
  analytics: "/analytics",
  admin: "/knowledge",
  settings: "/settings",
  widgetDocs: "/widget-guide",
};

function viewFromPath(pathname: string): View {
  if (pathname.startsWith("/live")) return "live";
  if (pathname.startsWith("/history")) return "history";
  if (pathname.startsWith("/tickets")) return "tickets";
  if (pathname.startsWith("/analytics")) return "analytics";
  if (pathname.startsWith("/knowledge")) return "admin";
  if (pathname.startsWith("/settings")) return "settings";
  if (pathname.startsWith("/widget-guide")) return "widgetDocs";
  return "history";
}

function conversationIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/(?:live|history)\/(\d+)\/?$/);
  return match ? Number(match[1]) : null;
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
  const { sites, selectedSiteId, current, isLoading, createSite, isOwner } =
    useSite();
  const { showToast } = useToast();
  const selectedConversationId = conversationIdFromPath(location.pathname);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Collapse the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const { data: conversations, mutate: mutateConversations } = useSWR(
    selectedSiteId != null ? conversationsKey(selectedSiteId) : null,
    () => listConversations(selectedSiteId as number)
  );
  const { mutate: mutateAnalytics } = useSWR(
    selectedSiteId != null ? analyticsKey(selectedSiteId) : null,
    () => getAnalytics(selectedSiteId as number)
  );
  const { data: settings } = useSWR(
    selectedSiteId != null ? settingsKey(selectedSiteId) : null,
    () => getSettings(selectedSiteId as number),
  );
  const liveEnabled = Boolean(
    settings?.live_human_escalation_available && settings.live_human_escalation_enabled,
  );

  // Tickets are shared between the sidebar badge and the Tickets page so the
  // two can never disagree.
  const { data: callbacks, mutate: mutateCallbacks } = useSWR(
    liveEnabled && selectedSiteId != null ? callbacksKey(selectedSiteId) : null,
    () => listCallbacks(selectedSiteId as number),
    { refreshInterval: 5000 },
  );
  const { data: operators } = useSWR(
    liveEnabled && selectedSiteId != null ? operatorsKey(selectedSiteId) : null,
    () => listOperators(selectedSiteId as number),
  );
  // In-progress tickets already have someone on them; the badge is "needs
  // attention".
  const pendingTicketCount =
    callbacks?.filter((item) => item.status === "pending" && !item.archived).length ?? 0;
  const { userId } = useAuth();

  const patchTicket = async (
    id: number,
    request: () => Promise<CallbackTicket>,
    apply: (ticket: CallbackTicket) => CallbackTicket,
    failMessage: string,
  ) => {
    try {
      await mutateCallbacks(
        async (list) => {
          const updated = await request();
          return list?.map((item) => (item.id === updated.id ? updated : item)) ?? [];
        },
        {
          optimisticData: (list) =>
            list?.map((item) => (item.id === id ? apply(item) : item)) ?? [],
          rollbackOnError: true,
          revalidate: false,
        }
      );
    } catch {
      showToast(failMessage);
    }
  };

  const onMoveTicket = async (id: number, status: TicketStatus) => {
    if (selectedSiteId == null) return;
    await patchTicket(
      id,
      () => setCallbackStatus(selectedSiteId, id, status),
      (item) => ({
        ...item,
        status,
        resolved_at: status === "resolved" ? new Date().toISOString() : null,
        // Mirror the server's auto-assign so the chip updates instantly.
        assignee_user_id:
          status === "in_progress" && !item.assignee_user_id && userId
            ? userId
            : item.assignee_user_id,
      }),
      "Couldn't move the ticket. Restored.",
    );
  };

  const onAssignTicket = async (id: number, assignee: string | null) => {
    if (selectedSiteId == null) return;
    await patchTicket(
      id,
      () => assignCallback(selectedSiteId, id, assignee),
      (item) => ({ ...item, assignee_user_id: assignee }),
      "Couldn't reassign the ticket. Restored.",
    );
  };

  const onSetTicketArchived = async (id: number, archived: boolean) => {
    if (selectedSiteId == null) return;
    await patchTicket(
      id,
      () => archiveCallback(selectedSiteId, id, archived),
      (item) => ({ ...item, archived }),
      archived ? "Couldn't archive the ticket. Restored." : "Couldn't unarchive the ticket. Restored.",
    );
  };

  const onInboxWaiting = useCallback((id: number) => {
    void mutateConversations(
      (current) => current?.map((conversation) => (
        conversation.id === id ? { ...conversation, mode: "waiting" as const } : conversation
      )),
      { revalidate: true },
    );
  }, [mutateConversations]);
  const onInboxTransition = useCallback((state: Partial<LiveState> & {
    conversation_id: number;
  }) => {
    void mutateConversations(
      (current) => current?.map((conversation) => (
        conversation.id === state.conversation_id ? {
          ...conversation,
          ...(state.mode ? { mode: state.mode } : {}),
          ...(state.assigned_user_id !== undefined
            ? { assigned_user_id: state.assigned_user_id }
            : {}),
          ...(state.closed_at !== undefined ? { closed_at: state.closed_at } : {}),
        } : conversation
      )),
      { revalidate: true },
    );
  }, [mutateConversations]);
  const inbox = useLiveInbox(
    selectedSiteId,
    liveEnabled,
    onInboxWaiting,
    onInboxTransition,
  );

  const selectedConversation = conversations?.find(
    (c) => c.id === selectedConversationId
  );

  // Keep route membership aligned with the live/history state partition.
  useEffect(() => {
    if (selectedConversationId === null || !conversations) return;
    const selected = conversations.find((conversation) => conversation.id === selectedConversationId);
    if (!selected) {
      navigate(view === "live" ? "/live" : "/history", { replace: true });
      return;
    }
    const active = selected.mode === "waiting" || selected.mode === "human";
    if (view === "live" && !active) navigate(`/history/${selected.id}`, { replace: true });
    if (view === "history" && active) navigate(`/live/${selected.id}`, { replace: true });
  }, [conversations, navigate, selectedConversationId, view]);

  const onNewChat = () => {
    setSidebarOpen(false);
    navigate("/history");
  };

  const onSelectConversation = (id: number, section: "live" | "history") => {
    setSidebarOpen(false);
    navigate(`/${section}/${id}`);
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
                mode: "ai",
                assigned_user_id: null,
                escalation_requested_at: null,
                accepted_at: null,
                closed_at: null,
                last_message_at: null,
              },
              ...prev,
            ]
          : prev,
      { revalidate: true }
    );
    navigate(`/history/${id}`);
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
    if (id === selectedConversationId) navigate("/history");
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
    navigate(`/history/${id}`);
  };

  const onLiveStateChange = useCallback((state: LiveState) => {
    void mutateConversations(
      (current) => current?.map((conversation) => conversation.id === state.conversation_id ? {
        ...conversation,
        mode: state.mode,
        assigned_user_id: state.assigned_user_id,
        escalation_requested_at: state.escalation_requested_at,
        accepted_at: state.accepted_at,
        closed_at: state.closed_at,
      } : conversation),
      { revalidate: true },
    );
    if (conversationIdFromPath(location.pathname) === state.conversation_id) {
      const section = state.mode === "waiting" || state.mode === "human" ? "live" : "history";
      const target = `/${section}/${state.conversation_id}`;
      if (location.pathname !== target) navigate(target, { replace: true });
    }
  }, [location.pathname, mutateConversations, navigate]);

  if (!isLoading && sites && sites.length === 0) {
    return <FirstRunPanel onCreate={createSite} />;
  }

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        view={view}
        liveEnabled={liveEnabled}
        ticketsPendingCount={pendingTicketCount}
        liveOnline={inbox.online}
        liveConnected={inbox.connected}
        liveError={inbox.error}
        businessName={current?.name}
        assistantName={current?.assistant_name}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={onNewChat}
        onSelectConversation={onSelectConversation}
        onSetLiveOnline={inbox.setOnline}
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

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
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
            element={settings === undefined ? <div /> : <Navigate to={liveEnabled ? "/live" : "/history"} replace />}
          />
          <Route
            path="/live/:conversationId?"
            element={liveEnabled ? (
              <ChatPage
                section="live"
                selectedConversationId={selectedConversationId}
                selectedConversation={selectedConversation}
                settings={settings}
                liveEnabled={liveEnabled}
                onConversationCreated={onConversationCreated}
                onRate={onRate}
                onLiveStateChange={onLiveStateChange}
              />
            ) : <Navigate to="/history" replace />}
          />
          <Route
            path="/history/:conversationId?"
            element={
              <ChatPage
                section="history"
                selectedConversationId={selectedConversationId}
                selectedConversation={selectedConversation}
                settings={settings}
                liveEnabled={liveEnabled}
                onConversationCreated={onConversationCreated}
                onRate={onRate}
                onLiveStateChange={onLiveStateChange}
              />
            }
          />
          <Route
            path="/tickets"
            element={liveEnabled ? (
              <TicketsPage
                callbacks={callbacks}
                operators={operators}
                isOwner={isOwner}
                currentUserId={userId}
                onMove={onMoveTicket}
                onAssign={onAssignTicket}
                onSetArchived={onSetTicketArchived}
              />
            ) : <Navigate to="/history" replace />}
          />
          <Route path="/knowledge" element={<AdminPage />} />
          {/* Site settings are owner-only; members are bounced to history. */}
          <Route
            path="/settings"
            element={isOwner ? <SettingsPage /> : <Navigate to="/history" replace />}
          />
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
