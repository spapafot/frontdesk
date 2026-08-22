import { useCallback, useRef, useState } from "react";
import {
  Source,
  ProductResults,
  StreamEvent,
  ToolCall,
  formatChatError,
  streamChat,
} from "../api/chat";
import { getConversationMessages } from "../api/conversations";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCall[];
  sources: Source[];
  productResults: ProductResults | null;
}

interface Options {
  onConversationCreated?: (id: number) => void;
  siteId: number | null;
}

let counter = 0;
const nextId = () => `${Date.now()}-${counter++}`;

export function useChatStream(options?: Options) {
  const siteId = options?.siteId ?? null;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const conversationRef = useRef<number | null>(null);

  const updateAssistant = useCallback(
    (id: string, updater: (msg: ChatMessage) => ChatMessage) => {
      setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
    },
    []
  );

  const setConversation = useCallback(async (id: number | null) => {
    if (id === conversationRef.current) return;
    conversationRef.current = id;
    if (id === null || siteId === null) {
      setMessages([]);
      return;
    }
    // Clear immediately so the chat window shows history skeletons rather than
    // the previously selected conversation's messages while this one loads.
    setMessages([]);
    setIsLoadingHistory(true);
    try {
      const stored = await getConversationMessages(siteId, id);
      setMessages(
        stored.map((m, i) => ({
          id: `${id}-${i}`,
          role: m.role,
          content: m.content,
          toolCalls: [],
          sources: [],
          productResults: null,
        }))
      );
    } catch {
      setMessages([]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [siteId]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      const wasNew = conversationRef.current === null;

      const userMessage: ChatMessage = {
        id: nextId(),
        role: "user",
        content: trimmed,
        toolCalls: [],
        sources: [],
        productResults: null,
      };
      const assistantId = nextId();
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        sources: [],
        productResults: null,
      };
      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);

      const onEvent = (event: StreamEvent) => {
        switch (event.type) {
          case "conversation":
            conversationRef.current = event.conversation_id;
            if (wasNew) options?.onConversationCreated?.(event.conversation_id);
            break;
          case "tool_call":
            updateAssistant(assistantId, (m) => ({
              ...m,
              toolCalls: [
                ...m.toolCalls,
                { name: event.name, arguments: event.arguments, result: event.result },
              ],
            }));
            break;
          case "sources":
            updateAssistant(assistantId, (m) => ({ ...m, sources: event.sources }));
            break;
          case "product_results":
            updateAssistant(assistantId, (m) => ({
              ...m,
              productResults: {
                products: event.products,
                page: event.page,
                has_more: event.has_more,
              },
            }));
            break;
          case "token":
            updateAssistant(assistantId, (m) => ({ ...m, content: m.content + event.content }));
            break;
          case "error":
            updateAssistant(assistantId, (m) => ({
              ...m,
              content: [
                m.content,
                `\u26a0\ufe0f ${formatChatError(event)}`,
              ]
                .filter(Boolean)
                .join("\n\n"),
            }));
            break;
          case "input_blocked":
            setMessages((prev) =>
              prev
                .filter((message) => message.id !== userMessage.id)
                .map((message) =>
                  message.id === assistantId
                    ? { ...message, content: `\u26a0\ufe0f ${event.message}` }
                    : message
                )
            );
            break;
          case "done":
            break;
        }
      };

      try {
        await streamChat(
          { message: trimmed, conversationId: conversationRef.current, siteId },
          onEvent
        );
      } catch (err) {
        updateAssistant(assistantId, (m) => ({
          ...m,
          content: m.content || `\u26a0\ufe0f ${(err as Error).message}`,
        }));
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, options, siteId, updateAssistant]
  );

  return { messages, isStreaming, isLoadingHistory, send, setConversation };
}
