import { useEffect } from "react";
import useSWR from "swr";
import { Rating } from "../api/conversations";
import { getSettings, settingsKey } from "../api/settings";
import { ChatInput } from "../components/ChatInput";
import { ChatWindow } from "../components/ChatWindow";
import { DebugPanel } from "../components/DebugPanel";
import { RatingControl } from "../components/RatingControl";
import { useChatStream } from "../hooks/useChatStream";
import { useState } from "react";

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
  const { messages, isStreaming, send, setConversation } = useChatStream({
    onConversationCreated,
  });
  const [showDebug, setShowDebug] = useState(false);
  const { data: settings } = useSWR(settingsKey, getSettings);

  useEffect(() => {
    setConversation(selectedConversationId);
  }, [selectedConversationId, setConversation]);

  const hasAssistantReply = messages.some((m) => m.role === "assistant" && m.content);
  const canRate = selectedConversationId !== null && hasAssistantReply;

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div>
          <h1 className="text-sm font-semibold text-slate-800">
            {settings?.assistant_name ?? "AI Assistant"}
          </h1>
          <p className="text-xs text-slate-500">
            {settings ? settings.business_name : "Ask about anything in our knowledge base"}
          </p>
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
      </header>
      <ChatWindow messages={messages} showDebug={showDebug} />
      <ChatInput onSend={send} disabled={isStreaming} />
    </div>
  );
}
