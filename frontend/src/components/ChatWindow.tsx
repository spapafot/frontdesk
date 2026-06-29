import { useEffect, useRef } from "react";
import { ChatMessage } from "../hooks/useChatStream";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
  showDebug: boolean;
}

export function ChatWindow({ messages, showDebug }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.length === 0 && (
        <div className="mx-auto mt-10 max-w-md text-center text-sm text-slate-500">
          <p className="text-base font-medium text-slate-700">How can I help you?</p>
          <p className="mt-2">
            Ask a question and I'll answer using the information in our knowledge base.
          </p>
        </div>
      )}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} showDebug={showDebug} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
