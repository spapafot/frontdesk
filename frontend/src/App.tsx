import { useEffect, useState } from "react";
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
import { VoicePage } from "./pages/VoicePage";

const SELECTED_KEY = "selectedConversationId";

function loadSelectedId(): number | null {
  const raw = localStorage.getItem(SELECTED_KEY);
  if (!raw) return null;
  const id = Number(raw);
  return Number.isFinite(id) ? id : null;
}

export default function App() {
  const [view, setView] = useState<View>("chat");
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(
    loadSelectedId
  );

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
    setView("chat");
  };

  const onSelectConversation = (id: number) => {
    setSelectedConversationId(id);
    setView("chat");
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
    setView("chat");
  };

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        selectedConversationId={selectedConversationId}
        view={view}
        businessName={settings?.business_name}
        assistantName={settings?.assistant_name}
        onNewChat={onNewChat}
        onSelectConversation={onSelectConversation}
        onNavigate={setView}
        onRenameConversation={onRenameConversation}
        onDeleteConversation={onDeleteConversation}
      />
      <main className="min-h-0 min-w-0 flex-1">
        {view === "chat" && (
          <ChatPage
            selectedConversationId={selectedConversationId}
            rating={selectedConversation?.rating ?? null}
            onConversationCreated={onConversationCreated}
            onRate={onRate}
          />
        )}
        {view === "voice" && (
          <VoicePage
            selectedConversationId={selectedConversationId}
            onConversationCreated={onConversationCreated}
          />
        )}
        {view === "admin" && <AdminPage />}
        {view === "settings" && <SettingsPage />}
        {view === "analytics" && (
          <AnalyticsPage onOpenConversation={onOpenConversation} />
        )}
      </main>
    </div>
  );
}
