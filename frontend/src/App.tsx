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
import { getSettings, settingsKey } from "./api/settings";
import { Sidebar, View } from "./components/Sidebar";
import { AdminPage } from "./pages/AdminPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ChatPage } from "./pages/ChatPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WidgetDocsPage } from "./pages/WidgetDocsPage";

const SELECTED_KEY = "selectedConversationId";

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

function loadSelectedId(): number | null {
  const raw = localStorage.getItem(SELECTED_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) ? id : null;
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const view = viewFromPath(location.pathname);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(
    loadSelectedId
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Collapse the mobile drawer whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const { data: conversations, mutate: mutateConversations } = useSWR(
    conversationsKey,
    listConversations
  );
  const { data: settings } = useSWR(settingsKey, getSettings);
  const { mutate: mutateAnalytics } = useSWR(analyticsKey, getAnalytics);

  const selectedConversation = conversations?.find(
    (c) => c.id === selectedConversationId
  );

  // Persist the selected conversation across reloads.
  useEffect(() => {
    if (selectedConversationId === null) localStorage.removeItem(SELECTED_KEY);
    else localStorage.setItem(SELECTED_KEY, String(selectedConversationId));
  }, [selectedConversationId]);

  // If the persisted conversation no longer exists, clear the selection.
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
    await renameConversation(id, title);
    mutateConversations();
  };

  const onDeleteConversation = async (id: number) => {
    await deleteConversation(id);
    if (id === selectedConversationId) setSelectedConversationId(null);
    mutateConversations();
    mutateAnalytics();
  };

  const onRate = async (id: number, rating: Rating) => {
    await rateConversation(id, rating);
    mutateConversations();
    mutateAnalytics();
  };

  const onOpenConversation = (id: number) => {
    setSelectedConversationId(id);
    navigate("/");
  };

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        view={view}
        businessName={settings?.business_name}
        assistantName={settings?.assistant_name}
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
            {settings?.assistant_name ?? "Plug & Play"}
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
