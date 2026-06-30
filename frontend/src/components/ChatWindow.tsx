import { useEffect, useRef } from "react";
import { ChatMessage } from "../hooks/useChatStream";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
  showDebug: boolean;
  onSpeak?: (text: string) => void;
}

export function ChatWindow({ messages, showDebug, onSpeak }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full max-w-2xl space-y-4 p-4">
        {messages.length === 0 && (
          <div className="mx-auto mt-10 max-w-md text-center text-sm text-slate-500">
            <p className="text-base font-medium text-slate-700">How can I help you?</p>
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
            onSpeak={onSpeak}
          />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
