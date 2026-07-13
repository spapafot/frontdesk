import { useEffect, useState } from "react";
import useSWR from "swr";
import { Rating } from "../api/conversations";
import { getSettings, settingsKey } from "../api/settings";
import { ChatInput } from "../components/ChatInput";
import { ChatWindow } from "../components/ChatWindow";
import { DebugPanel } from "../components/DebugPanel";
import { RatingControl } from "../components/RatingControl";
import { Skeleton } from "../components/Skeleton";
import { useSite } from "../components/SiteProvider";
import { useChatStream } from "../hooks/useChatStream";

interface Props {
  selectedConversationId: number | null;
  rating: Rating | null;
  onConversationCreated: (id: number) => void;
  onRate: (id: number, rating: Rating) => void | Promise<void>;
}

export function ChatPage({
  selectedConversationId,
  rating,
  onConversationCreated,
  onRate,
}: Props) {
  const [showDebug, setShowDebug] = useState(false);
  const { selectedSiteId } = useSite();
  const { messages, isStreaming, isLoadingHistory, send, setConversation } = useChatStream({
    onConversationCreated,
    siteId: selectedSiteId,
  });
  const { data: settings } = useSWR(
    selectedSiteId != null ? settingsKey(selectedSiteId) : null,
    () => getSettings(selectedSiteId as number)
  );

  useEffect(() => {
    setConversation(selectedConversationId);
  }, [selectedConversationId, setConversation]);

  const hasAssistantReply = messages.some((m) => m.role === "assistant" && m.content);
  const canRate = selectedConversationId !== null && hasAssistantReply;

  return (
    <div className="flex h-full flex-col">
      <header className="px-4 pt-4">
        <div className="mx-auto flex w-full max-w-2xl items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
        <div>
          {settings ? (
            <>
              <h1 className="text-sm font-semibold text-slate-800">
                {settings.assistant_name}
              </h1>
              <p className="text-xs text-slate-500">{settings.business_name}</p>
            </>
          ) : (
            <div role="status" aria-label="Loading assistant">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="mt-1.5 h-3 w-40" />
            </div>
          )}
        </div>
        <div className="flex items-center gap-4">
          {canRate && (
            <RatingControl
              rating={rating}
              disabled={isStreaming}
              onSubmit={(value) => onRate(selectedConversationId as number, value)}
            />
          )}
          <DebugPanel enabled={showDebug} onToggle={setShowDebug} />
        </div>
        </div>
      </header>
      <ChatWindow
        messages={messages}
        showDebug={showDebug}
        isLoadingHistory={isLoadingHistory}
      />
      <ChatInput onSend={send} disabled={isStreaming} />
    </div>
  );
}
