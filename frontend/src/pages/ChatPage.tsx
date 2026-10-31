import { useEffect, useState } from "react";
import useSWR from "swr";
import { ConversationSummary, getConversationMessages, Rating } from "../api/conversations";
import { LiveMessage, LiveState } from "../api/live";
import { Settings } from "../api/settings";
import { ChatInput } from "../components/ChatInput";
import { ChatWindow } from "../components/ChatWindow";
import { DebugPanel } from "../components/DebugPanel";
import { LiveConversation } from "../components/LiveConversation";
import { RatingControl } from "../components/RatingControl";
import { Skeleton } from "../components/Skeleton";
import { useSite } from "../components/SiteProvider";
import { useChatStream } from "../hooks/useChatStream";
import { useLiveConversation } from "../hooks/useLiveSupport";

const noop = () => {};

interface Props {
  section: "live" | "history";
  selectedConversationId: number | null;
  selectedConversation?: ConversationSummary;
  settings?: Settings;
  liveEnabled: boolean;
  onConversationCreated: (id: number) => void;
  onRate: (id: number, rating: Rating) => void | Promise<void>;
  onLiveStateChange: (state: LiveState) => void;
}

export function ChatPage({
  section,
  selectedConversationId,
  selectedConversation,
  settings,
  liveEnabled,
  onConversationCreated,
  onRate,
  onLiveStateChange,
}: Props) {
  const [showDebug, setShowDebug] = useState(false);
  const { selectedSiteId } = useSite();
  const selectedMode = selectedConversation?.mode;
  const isAiConversation = section === "history" && selectedMode === "ai";
  // A visitor's AI conversation is a record of what happened on the website, so
  // it's read-only: sending here would append messages as if the visitor wrote
  // them. Only the admin's own test chat (no visitor session) accepts input.
  const isReadOnlyAiConversation =
    isAiConversation && selectedConversation?.is_visitor === true;
  // Active conversations need the live socket; closed/pending ones are terminal
  // history read straight from stored messages, so they stay viewable even when
  // live support is turned off (which disables the socket).
  const isLiveConversation = selectedMode === "waiting" || selectedMode === "human";
  const isClosedTranscript = selectedMode === "closed" || selectedMode === "pending_ticket";
  const { messages, isStreaming, isLoadingHistory, send, setConversation } = useChatStream({
    onConversationCreated,
    siteId: selectedSiteId,
  });
  const live = useLiveConversation(
    selectedSiteId,
    selectedConversationId,
    liveEnabled && isLiveConversation,
    onLiveStateChange,
  );
  const transcriptKey = isClosedTranscript && selectedSiteId != null && selectedConversationId != null
    ? `conversation-transcript:${selectedSiteId}:${selectedConversationId}`
    : null;
  const { data: storedTranscript, error: transcriptError } = useSWR(
    transcriptKey,
    () => getConversationMessages(selectedSiteId as number, selectedConversationId as number),
  );
  const transcriptState: LiveState | null =
    isClosedTranscript && storedTranscript && selectedConversationId !== null
      ? {
          conversation_id: selectedConversationId,
          profile_id: 0,
          mode: selectedMode as LiveState["mode"],
          assigned_user_id: selectedConversation?.assigned_user_id ?? null,
          escalation_requested_at: selectedConversation?.escalation_requested_at ?? null,
          escalation_expires_at: null,
          accepted_at: selectedConversation?.accepted_at ?? null,
          closed_at: selectedConversation?.closed_at ?? null,
          messages: storedTranscript.map((message): LiveMessage => ({
            id: message.id,
            client_message_id: null,
            role: message.role,
            content: message.content,
            sender_type: message.sender_type,
            sender_user_id: null,
            sender_display_name: message.sender_display_name,
            created_at: message.created_at,
          })),
        }
      : null;
  useEffect(() => {
    setConversation(isAiConversation ? selectedConversationId : null);
  }, [isAiConversation, selectedConversationId, setConversation]);

  const hasAssistantReply = messages.some((message) => (
    message.role === "assistant" && message.content
  ));
  const canRate = isAiConversation && selectedConversationId !== null && hasAssistantReply;

  return (
    <div className="flex h-full flex-col">
      <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex w-full items-center justify-between gap-4">
          <div>
            {settings ? (
              <>
                <h1 className="text-lg font-semibold text-slate-900">
                  {section === "live" ? "Live support" : settings.assistant_name}
                </h1>
                <p className="mt-0.5 text-sm text-slate-500">{settings.business_name}</p>
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
                rating={selectedConversation?.rating ?? null}
                disabled={isStreaming}
                onSubmit={(value) => onRate(selectedConversationId as number, value)}
              />
            )}
            {isAiConversation && (
              <DebugPanel enabled={showDebug} onToggle={setShowDebug} />
            )}
          </div>
        </div>
      </header>

      {selectedConversationId === null && section === "live" ? (
        <div className="mx-auto flex w-full max-w-2xl flex-1 items-center justify-center px-4 text-center text-sm text-slate-500">
          Waiting and active conversations will appear here.
        </div>
      ) : isLiveConversation ? (
        live.state ? (
          <LiveConversation
            state={live.state}
            error={live.error}
            onAction={live.action}
            visitorTyping={live.visitorTyping}
            onTyping={live.notifyTyping}
          />
        ) : (
          <div className="mx-auto w-full max-w-2xl flex-1 space-y-3 p-4" role="status" aria-label="Loading live conversation">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-12 w-2/3 rounded-xl" />
          </div>
        )
      ) : isClosedTranscript ? (
        transcriptState ? (
          <LiveConversation state={transcriptState} error={null} onAction={noop} />
        ) : transcriptError ? (
          <div className="mx-auto flex w-full max-w-2xl flex-1 items-center justify-center px-4 text-center text-sm text-red-600">
            Couldn't load this conversation.
          </div>
        ) : (
          <div className="mx-auto w-full max-w-2xl flex-1 space-y-3 p-4" role="status" aria-label="Loading conversation">
            <Skeleton className="h-16 w-full rounded-xl" />
            <Skeleton className="h-12 w-2/3 rounded-xl" />
          </div>
        )
      ) : (
        <>
          <ChatWindow
            messages={messages}
            showDebug={showDebug}
            isLoadingHistory={isLoadingHistory}
          />
          {isReadOnlyAiConversation ? (
            <div className="border-t border-slate-200 bg-white px-6 py-4">
              <p className="mx-auto w-full max-w-3xl text-center text-sm text-slate-500">
                This conversation happened on your website. It's a read-only record.
              </p>
            </div>
          ) : (
            <ChatInput onSend={send} disabled={isStreaming} />
          )}
        </>
      )}
    </div>
  );
}
