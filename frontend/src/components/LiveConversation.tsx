import { FormEvent, useEffect, useRef, useState } from "react";
import { LiveState } from "../api/live";

export function LiveConversation({
  state,
  error,
  onAction,
  visitorTyping = false,
  onTyping,
}: {
  state: LiveState;
  error: string | null;
  onAction: (type: string, payload?: object) => void;
  visitorTyping?: boolean;
  onTyping?: (active: boolean) => void;
}) {
  const [message, setMessage] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const messages = state.messages ?? [];
  const lastMessageId = messages.length ? messages[messages.length - 1].id : null;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lastMessageId, visitorTyping]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const content = message.trim();
    if (!content || state.mode !== "human") return;
    onAction("message", { content, client_message_id: crypto.randomUUID() });
    setMessage("");
    onTyping?.(false);
  };

  const status = {
    ai: null,
    waiting: {
      title: "Visitor waiting",
      description: "Accept this request to start a live conversation.",
      className: "border-amber-200 bg-amber-50 text-amber-950",
    },
    human: {
      title: "Live support active",
      description: "You are chatting directly with this visitor. AI cannot resume in this conversation.",
      className: "border-sky-200 bg-sky-50 text-sky-950",
    },
    pending_ticket: {
      title: "No operator accepted",
      description: "The visitor can leave their details for a callback.",
      className: "border-amber-200 bg-amber-50 text-amber-950",
    },
    closed: {
      title: "Conversation ended",
      description: "This conversation is closed. The visitor can start a new conversation.",
      className: "border-slate-200 bg-slate-50 text-slate-800",
    },
  }[state.mode];

  const senderLabel = (senderType: string, displayName: string | null) => {
    if (senderType === "operator") return displayName || "Support agent";
    if (senderType === "ai") return "AI assistant";
    return displayName;
  };

  const composerPlaceholder =
    state.mode === "human"
      ? "Reply to visitor…"
      : state.mode === "closed"
        ? "This conversation has ended"
        : "Accept the conversation to reply";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {status && (
        <div className="px-6 pt-5">
          <div className={`mx-auto flex w-full max-w-3xl items-center justify-between gap-4 rounded-2xl border px-5 py-4 ${status.className}`}>
            <div className="min-w-0">
              <p className="text-sm font-semibold">{status.title}</p>
              <p className="mt-0.5 text-xs opacity-75">{status.description}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {state.mode === "waiting" && (
                <button
                  type="button"
                  className="rounded-lg bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-amber-800"
                  onClick={() => onAction("accept")}
                >
                  Accept request
                </button>
              )}
              {state.mode === "human" && (
                <button
                  type="button"
                  className="rounded-lg border border-sky-300 bg-white px-3 py-1.5 text-xs font-semibold text-sky-800 transition hover:bg-sky-100"
                  onClick={() => onAction("close")}
                >
                  End conversation
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto w-full max-w-3xl space-y-3">
          {messages.map((item) => {
            const visitor = item.sender_type === "visitor";
            const label = senderLabel(item.sender_type, item.sender_display_name);
            return (
              <div key={item.id} className={`flex ${visitor ? "justify-start" : "justify-end"}`}>
                <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${visitor ? "rounded-bl-sm border border-slate-200 bg-white text-slate-800 shadow-sm" : item.sender_type === "operator" ? "rounded-br-sm bg-sky-600 text-white" : "rounded-br-sm border border-sky-200 bg-sky-50 text-sky-950"}`}>
                  {label && <div className="mb-0.5 text-[11px] font-medium opacity-70">{label}</div>}
                  {item.content}
                </div>
              </div>
            );
          })}
          {visitorTyping && (
            <div className="flex justify-start">
              <div
                className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm"
                role="status"
                aria-label="Visitor is typing"
              >
                <span className="inline-flex gap-1 text-slate-400">
                  <span className="animate-pulse">●</span>
                  <span className="animate-pulse [animation-delay:150ms]">●</span>
                  <span className="animate-pulse [animation-delay:300ms]">●</span>
                </span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>
      {error && <p className="mx-auto w-full max-w-2xl px-4 pb-2 text-xs text-red-600">{error}</p>}
      <div className="border-t border-slate-200 bg-white p-4">
        <form onSubmit={submit} className="mx-auto flex w-full max-w-3xl gap-2">
          <input
            value={message}
            onChange={(event) => {
              setMessage(event.target.value);
              if (state.mode === "human") onTyping?.(event.target.value.trim().length > 0);
            }}
            disabled={state.mode !== "human"}
            placeholder={composerPlaceholder}
            className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-sky-500 disabled:bg-slate-50"
          />
          <button disabled={state.mode !== "human" || !message.trim()} className="rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50">Send</button>
        </form>
      </div>
    </div>
  );
}
