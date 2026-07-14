import { useEffect, useState } from "react";
import useSWR from "swr";
import { ConversationSummary, getConversationMessages, Rating } from "../api/conversations";
import { LiveMessage, LiveState, listCallbacks, resolveCallback } from "../api/live";
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
  const callbacksKey = liveEnabled && selectedSiteId != null && section === "history"
    ? `live-callbacks:${selectedSiteId}`
    : null;
  const { data: callbacks, mutate: mutateCallbacks } = useSWR(
    callbacksKey,
    () => listCallbacks(selectedSiteId as number),
    { refreshInterval: 5000 },
  );

  useEffect(() => {
    setConversation(isAiConversation ? selectedConversationId : null);
  }, [isAiConversation, selectedConversationId, setConversation]);

  const hasAssistantReply = messages.some((message) => (
    message.role === "assistant" && message.content
  ));
  const canRate = isAiConversation && selectedConversationId !== null && hasAssistantReply;

  return (
    <div className="flex h-full flex-col">
      <header className="px-4 pt-4">
        <div className="mx-auto flex w-full max-w-2xl items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div>
            {settings ? (
              <>
                <h1 className="text-sm font-semibold text-slate-800">
                  {section === "live" ? "Live support" : settings.assistant_name}
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

      {callbacks?.some((item) => item.status === "pending") && (
        <div className="mx-auto mt-2 flex w-full max-w-2xl flex-wrap gap-2 px-4">
          {callbacks.filter((item) => item.status === "pending").map((item) => (
            <div key={item.id} className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              <span>Callback: {item.customer_name || item.customer_email}</span>
              <button className="font-semibold underline" onClick={() => void navigator.clipboard.writeText(item.customer_email)}>Copy email</button>
              <button className="font-semibold underline" onClick={async () => {
                await resolveCallback(selectedSiteId as number, item.id);
                await mutateCallbacks();
              }}>Resolve</button>
            </div>
          ))}
        </div>
      )}

      {selectedConversationId === null && section === "live" ? (
        <div className="mx-auto flex w-full max-w-2xl flex-1 items-center justify-center px-4 text-center text-sm text-slate-500">
          Waiting and active conversations will appear here.
        </div>
      ) : isLiveConversation ? (
        live.state ? (
          <LiveConversation state={live.state} error={live.error} onAction={live.action} />
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
          <ChatInput onSend={send} disabled={isStreaming} />
        </>
      )}
    </div>
  );
}
