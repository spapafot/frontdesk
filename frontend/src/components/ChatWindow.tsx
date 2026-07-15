import { useEffect, useRef } from "react";
import { ChatMessage } from "../hooks/useChatStream";
import { MessageBubble } from "./MessageBubble";
import { Skeleton } from "./Skeleton";

interface Props {
  messages: ChatMessage[];
  showDebug: boolean;
  isLoadingHistory?: boolean;
}

const HISTORY_SKELETON = [
  { side: "justify-end", w: "w-1/2" },
  { side: "justify-start", w: "w-3/4" },
  { side: "justify-end", w: "w-1/3" },
  { side: "justify-start", w: "w-2/3" },
];

export function ChatWindow({ messages, showDebug, isLoadingHistory }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-3xl space-y-4 px-6 py-6">
        {isLoadingHistory && (
          <div className="space-y-4" role="status" aria-label="Loading conversation">
            {HISTORY_SKELETON.map((b, idx) => (
              <div key={idx} className={`flex ${b.side}`}>
                <Skeleton className={`h-12 ${b.w} rounded-2xl`} />
              </div>
            ))}
          </div>
        )}
        {!isLoadingHistory && messages.length === 0 && (
          <div className="mx-auto mt-16 max-w-md text-center text-sm text-slate-500">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-100 text-xl text-sky-600">✦</div>
            <p className="text-base font-semibold text-slate-800">How can I help you?</p>
            <p className="mt-2">
              Upload a file and I'll answer your questions about the content.
            </p>
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            showDebug={showDebug}
          />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
