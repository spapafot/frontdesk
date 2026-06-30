import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { Rating } from "../api/conversations";
import { getSettings, settingsKey } from "../api/settings";
import { synthesizeSpeech } from "../api/speech";
import { ChatInput } from "../components/ChatInput";
import { ChatWindow } from "../components/ChatWindow";
import { DebugPanel } from "../components/DebugPanel";
import { RatingControl } from "../components/RatingControl";
import { useChatStream } from "../hooks/useChatStream";
import { SpeechQueue } from "../lib/speechQueue";

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
  const [voiceOutput, setVoiceOutput] = useState(false);
  const voiceOutputRef = useRef(voiceOutput);
  voiceOutputRef.current = voiceOutput;

  const voiceRef = useRef<string | undefined>(undefined);
  const speedRef = useRef<number>(1);
  const queueRef = useRef<SpeechQueue | null>(null);
  const getQueue = useCallback(() => {
    if (!queueRef.current) {
      queueRef.current = new SpeechQueue(
        (text) => synthesizeSpeech(text, voiceRef.current),
        () => speedRef.current
      );
    }
    return queueRef.current;
  }, []);

  // Manual replay of a finished message (plays the whole text, sentence by sentence).
  const speak = useCallback(
    (text: string) => {
      getQueue().speak(text);
    },
    [getQueue]
  );

  const { messages, isStreaming, send, conversationId, setConversation } = useChatStream({
    onConversationCreated,
    onAssistantStart: () => {
      if (voiceOutputRef.current) getQueue().start();
    },
    onAssistantToken: (delta) => {
      if (voiceOutputRef.current) getQueue().push(delta);
    },
    onAssistantDone: () => {
      if (voiceOutputRef.current) getQueue().flush();
    },
  });
  const { data: settings } = useSWR(settingsKey, getSettings);
  voiceRef.current = settings?.tts_voice;
  speedRef.current = settings?.tts_speed ?? 1.1;

  useEffect(() => {
    // Stop any playback only when genuinely switching to a different conversation -
    // NOT when the id is assigned to the new chat we're currently streaming into
    // (that would cancel the speech queue mid-reply).
    if (!isStreaming && selectedConversationId !== conversationId) {
      queueRef.current?.stop();
    }
    setConversation(selectedConversationId);
  }, [selectedConversationId, conversationId, isStreaming, setConversation]);

  useEffect(() => () => queueRef.current?.stop(), []);

  const hasAssistantReply = messages.some((m) => m.role === "assistant" && m.content);
  const canRate = selectedConversationId !== null && hasAssistantReply;

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-2xl items-center justify-between px-4 py-3">
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
          <button
            type="button"
            onClick={() =>
              setVoiceOutput((v) => {
                const next = !v;
                if (!next) queueRef.current?.stop();
                return next;
              })
            }
            title={voiceOutput ? "Voice replies on" : "Voice replies off"}
            className={`rounded-full px-2 py-1 text-xs font-medium transition ${
              voiceOutput
                ? "bg-sky-100 text-sky-700"
                : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            }`}
          >
            {voiceOutput ? "Voice on" : "Voice off"}
          </button>
          <DebugPanel enabled={showDebug} onToggle={setShowDebug} />
        </div>
        </div>
      </header>
      <ChatWindow messages={messages} showDebug={showDebug} onSpeak={speak} />
      <ChatInput onSend={send} disabled={isStreaming} />
    </div>
  );
}
