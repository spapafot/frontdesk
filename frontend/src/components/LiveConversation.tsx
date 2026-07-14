import { FormEvent, useState } from "react";
import { LiveState } from "../api/live";

export function LiveConversation({
  state,
  error,
  onAction,
}: {
  state: LiveState;
  error: string | null;
  onAction: (type: string, payload?: object) => void;
}) {
  const [message, setMessage] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const content = message.trim();
    if (!content || state.mode !== "human") return;
    onAction("message", { content, client_message_id: crypto.randomUUID() });
    setMessage("");
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

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {status && (
        <div className="px-4 pt-2">
          <div className={`mx-auto flex w-full max-w-2xl items-center justify-between gap-4 rounded-xl border px-4 py-3 ${status.className}`}>
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
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto w-full max-w-2xl space-y-3">
          {(state.messages ?? []).map((item) => {
            const visitor = item.sender_type === "visitor";
            const label = senderLabel(item.sender_type, item.sender_display_name);
            return (
              <div key={item.id} className={`flex ${visitor ? "justify-start" : "justify-end"}`}>
                <div className={`max-w-[75%] rounded-xl px-3 py-2 text-sm ${visitor ? "bg-slate-100 text-slate-800" : item.sender_type === "operator" ? "bg-sky-600 text-white" : "border border-sky-200 bg-sky-50 text-sky-950"}`}>
                  {label && <div className="mb-0.5 text-[11px] font-medium opacity-70">{label}</div>}
                  {item.content}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {error && <p className="mx-auto w-full max-w-2xl px-4 pb-2 text-xs text-red-600">{error}</p>}
      <div className="border-t border-slate-200 p-4">
        <form onSubmit={submit} className="mx-auto flex w-full max-w-2xl gap-2">
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            disabled={state.mode !== "human"}
            placeholder={state.mode === "human" ? "Reply to visitor…" : "Accept the conversation to reply"}
            className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-50"
          />
          <button disabled={state.mode !== "human" || !message.trim()} className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Send</button>
        </form>
      </div>
    </div>
  );
}
