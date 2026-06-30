import { useState } from "react";
import { ConversationSummary } from "../api/conversations";
import { ConfirmDialog } from "./ConfirmDialog";

export type View = "chat" | "voice" | "admin" | "settings" | "analytics";

interface Props {
  conversations: ConversationSummary[] | undefined;
  selectedConversationId: number | null;
  view: View;
  businessName?: string;
  assistantName?: string;
  onNewChat: () => void;
  onSelectConversation: (id: number) => void;
  onNavigate: (view: View) => void;
  onRenameConversation: (id: number, title: string) => void;
  onDeleteConversation: (id: number) => void;
}

function formatTime(startedAt: string): string {
  const date = new Date(startedAt);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Sidebar({
  conversations,
  selectedConversationId,
  view,
  businessName,
  assistantName,
  onNewChat,
  onSelectConversation,
  onNavigate,
  onRenameConversation,
  onDeleteConversation,
}: Props) {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ConversationSummary | null>(null);

  const startRename = (c: ConversationSummary) => {
    setEditingId(c.id);
    setDraft(c.title ?? "");
  };

  const commitRename = (id: number) => {
    const value = draft.trim();
    if (value) onRenameConversation(id, value);
    setEditingId(null);
    setDraft("");
  };

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-200 bg-slate-50">
      <div className="p-3">
        <button
          type="button"
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
        >
          <span className="text-lg leading-none">+</span> New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2">
        <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
          History
        </p>
        {conversations && conversations.length === 0 && (
          <p className="px-2 py-2 text-xs text-slate-400">No conversations yet.</p>
        )}
        <ul className="space-y-1">
          {conversations?.map((c) => {
            const active = view === "chat" && c.id === selectedConversationId;
            const title = c.title?.trim() || formatTime(c.started_at) || "Conversation";

            if (editingId === c.id) {
              return (
                <li key={c.id}>
                  <input
                    autoFocus
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={() => commitRename(c.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename(c.id);
                      if (e.key === "Escape") {
                        setEditingId(null);
                        setDraft("");
                      }
                    }}
                    maxLength={160}
                    className="w-full rounded-lg border border-sky-400 px-3 py-2 text-sm outline-none"
                  />
                </li>
              );
            }

            return (
              <li
                key={c.id}
                className={`group relative rounded-lg transition ${
                  active ? "bg-sky-100" : "hover:bg-slate-200"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectConversation(c.id)}
                  className="block w-full rounded-lg px-3 py-2 text-left transition-[padding] group-hover:pr-28"
                >
                  <span
                    className={`block truncate text-sm ${
                      active ? "text-sky-800" : "text-slate-700"
                    }`}
                  >
                    {title}
                  </span>
                  <span className="block truncate text-[11px] text-slate-400">
                    {formatTime(c.started_at)}
                  </span>
                </button>
                <div
                  className={`pointer-events-none absolute inset-y-0 right-0 hidden items-center gap-1 rounded-r-lg pr-2 group-hover:flex`}
                >
                  <button
                    type="button"
                    title="Rename"
                    onClick={() => startRename(c)}
                    className="pointer-events-auto rounded px-1.5 py-0.5 text-[11px] text-slate-500 hover:bg-slate-300"
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    title="Delete"
                    onClick={() => setPendingDelete(c)}
                    className="pointer-events-auto rounded px-1.5 py-0.5 text-[11px] text-red-500 hover:bg-red-100"
                  >
                    Delete
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="border-t border-slate-200 p-2">
        <button
          type="button"
          onClick={() => onNavigate("voice")}
          className={`mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
            view === "voice"
              ? "bg-sky-100 text-sky-800"
              : "text-slate-600 hover:bg-slate-200"
          }`}
        >
          Voice
        </button>
        <button
          type="button"
          onClick={() => onNavigate("analytics")}
          className={`mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
            view === "analytics"
              ? "bg-sky-100 text-sky-800"
              : "text-slate-600 hover:bg-slate-200"
          }`}
        >
          Logs & analytics
        </button>
        <button
          type="button"
          onClick={() => onNavigate("admin")}
          className={`mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
            view === "admin" ? "bg-sky-100 text-sky-800" : "text-slate-600 hover:bg-slate-200"
          }`}
        >
          Knowledge base
        </button>
        <button
          type="button"
          onClick={() => onNavigate("settings")}
          className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition ${
            view === "settings" ? "bg-sky-100 text-sky-800" : "text-slate-600 hover:bg-slate-200"
          }`}
        >
          Settings
        </button>
        <div className="mt-2 flex items-center gap-2 rounded-lg px-3 py-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-600 text-xs font-semibold text-white">
            {(businessName ?? "?").charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-slate-700">
              {businessName ?? "Account"}
            </p>
            <p className="truncate text-[11px] text-slate-400">
              {assistantName ?? "Assistant"}
            </p>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete conversation"
        message={
          pendingDelete
            ? `"${
                pendingDelete.title?.trim() || "this conversation"
              }" will be permanently deleted. This can't be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          if (pendingDelete) onDeleteConversation(pendingDelete.id);
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </aside>
  );
}
