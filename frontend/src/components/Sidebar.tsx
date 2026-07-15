import { useState } from "react";
import { ConversationSummary } from "../api/conversations";
import { useAuth } from "./AuthGate";
import { ConfirmDialog } from "./ConfirmDialog";
import { Skeleton } from "./Skeleton";
import { useSite } from "./SiteProvider";
import { SiteSwitcher } from "./SiteSwitcher";

export type View = "live" | "history" | "tickets" | "admin" | "settings" | "analytics" | "widgetDocs";

interface Props {
  conversations: ConversationSummary[] | undefined;
  selectedConversationId: number | null;
  view: View;
  liveEnabled: boolean;
  ticketsPendingCount: number;
  liveOnline: boolean;
  liveConnected: boolean;
  liveError: string | null;
  businessName?: string;
  assistantName?: string;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation: (id: number, section: "live" | "history") => void;
  onSetLiveOnline: (online: boolean) => void;
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
  liveEnabled,
  ticketsPendingCount,
  liveOnline,
  liveConnected,
  liveError,
  businessName,
  assistantName,
  open,
  onClose,
  onNewChat,
  onSelectConversation,
  onSetLiveOnline,
  onNavigate,
  onRenameConversation,
  onDeleteConversation,
}: Props) {
  const { canSignOut, signOut } = useAuth();
  const { isOwner } = useSite();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ConversationSummary | null>(null);
  const liveConversations = conversations?.filter((item) => (
    item.mode === "waiting" || item.mode === "human"
  ));
  const historyConversations = conversations?.filter((item) => (
    item.mode === "ai" || item.mode === "pending_ticket" || item.mode === "closed"
  ));
  const visibleConversations = view === "live"
    ? liveConversations
    : view === "history" ? historyConversations : undefined;

  const startRename = (conversation: ConversationSummary) => {
    setEditingId(conversation.id);
    setDraft(conversation.title ?? "");
  };
  const commitRename = (id: number) => {
    const value = draft.trim();
    if (value) onRenameConversation(id, value);
    setEditingId(null);
    setDraft("");
  };

  return (
    <aside className={`fixed inset-y-0 left-0 z-40 flex h-full w-64 flex-col border-r border-slate-200 bg-slate-50 transition-transform duration-200 md:static md:z-auto md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-3">
        <img src="/logo-horizontal-full-color.png" alt="Plug & Play" className="h-11 w-auto" />
        <button type="button" onClick={onClose} aria-label="Close menu" className="rounded-md p-1.5 text-slate-500 hover:bg-slate-200 md:hidden">×</button>
      </div>
      <SiteSwitcher />

      {liveEnabled && (
        <div className="space-y-1 border-b border-slate-200 p-2">
          <div className={`rounded-lg ${view === "live" ? "bg-sky-100" : ""}`}>
            <button type="button" onClick={() => onNavigate("live")} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium ${view === "live" ? "text-sky-800" : "text-slate-700 hover:bg-slate-200"}`}>
              <span className={`h-2 w-2 rounded-full ${liveConnected && liveOnline ? "bg-emerald-500" : "bg-slate-400"}`} />
              <span className="flex-1">Live support</span>
              {(liveConversations?.length ?? 0) > 0 && (
                <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-white">{liveConversations?.length}</span>
              )}
            </button>
            <button
              type="button"
              title={liveError ?? undefined}
              onClick={() => onSetLiveOnline(!liveOnline)}
              className="mb-1 ml-7 rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-600 shadow-sm"
            >
              {liveOnline ? "Online" : "Offline"}
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {view === "history" && (
          <button type="button" onClick={onNewChat} className="mb-2 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
            <span className="text-lg leading-none">+</span> New chat
          </button>
        )}
        {(view === "live" || view === "history") && conversations === undefined && (
          <div className="space-y-2" role="status" aria-label="Loading conversations">
            {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-11 w-full rounded-lg" />)}
          </div>
        )}
        {visibleConversations?.length === 0 && (
          <p className="px-2 py-3 text-xs text-slate-400">
            {view === "live" ? "No visitors are waiting or live." : "No conversations yet."}
          </p>
        )}
        <ul className="space-y-1">
          {visibleConversations?.map((conversation) => {
            const active = conversation.id === selectedConversationId;
            const title = conversation.title?.trim() || formatTime(conversation.started_at) || "Conversation";
            if (editingId === conversation.id) {
              return (
                <li key={conversation.id}>
                  <input autoFocus value={draft} onChange={(event) => setDraft(event.target.value)} onBlur={() => commitRename(conversation.id)} onKeyDown={(event) => {
                    if (event.key === "Enter") commitRename(conversation.id);
                    if (event.key === "Escape") setEditingId(null);
                  }} maxLength={160} className="w-full rounded-lg border border-sky-400 px-3 py-2 text-sm outline-none" />
                </li>
              );
            }
            const section = view as "live" | "history";
            return (
              <li key={conversation.id} className={`group relative rounded-lg ${active ? "bg-sky-100" : "hover:bg-slate-200"}`}>
                <button type="button" onClick={() => onSelectConversation(conversation.id, section)} className="block w-full rounded-lg px-3 py-2 text-left group-hover:pr-24">
                  <span className={`block truncate text-sm ${active ? "text-sky-800" : "text-slate-700"}`}>{title}</span>
                  <span className="flex items-center gap-1 text-[11px] text-slate-400">
                    {view === "live" && (
                      <span className={`font-semibold ${conversation.mode === "waiting" ? "text-amber-600" : "text-emerald-600"}`}>
                        {conversation.mode === "waiting" ? "Waiting" : "Live"}
                      </span>
                    )}
                    <span>{formatTime(conversation.last_message_at || conversation.started_at)}</span>
                  </span>
                </button>
                {view === "history" && (
                  <div className="pointer-events-none absolute inset-y-0 right-0 hidden items-center gap-1 pr-2 group-hover:flex">
                    <button type="button" onClick={() => startRename(conversation)} className="pointer-events-auto rounded px-1 text-[11px] text-slate-500 hover:bg-slate-300">Rename</button>
                    <button type="button" onClick={() => setPendingDelete(conversation)} className="pointer-events-auto rounded px-1 text-[11px] text-red-500 hover:bg-red-100">Delete</button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      <div className="border-t border-slate-200 p-2">
        {([
          ["settings", "Settings"],
          ["admin", "Knowledge base"],
        ] as const)
          // Site settings are owner-only; members never see the entry.
          .filter(([target]) => target !== "settings" || isOwner)
          .map(([target, label]) => (
          <button key={target} type="button" onClick={() => onNavigate(target)} className={`mb-1 flex w-full rounded-lg px-3 py-2 text-left text-sm ${view === target ? "bg-sky-100 text-sky-800" : "text-slate-600 hover:bg-slate-200"}`}>{label}</button>
        ))}
        <div className="mt-2 border-t border-slate-200 pt-2">
          {([
            ["history", "Chat history"],
            ["analytics", "Logs & analytics"],
            ["widgetDocs", "Widget guide"],
          ] as const).map(([target, label]) => (
            <button key={target} type="button" onClick={() => onNavigate(target)} className={`mb-1 flex w-full rounded-lg px-3 py-2 text-left text-sm ${view === target ? "bg-sky-100 text-sky-800" : "text-slate-600 hover:bg-slate-200"}`}>{label}</button>
          ))}
          {liveEnabled && (
            <button type="button" onClick={() => onNavigate("tickets")} className={`mb-1 flex w-full items-center rounded-lg px-3 py-2 text-left text-sm ${view === "tickets" ? "bg-sky-100 text-sky-800" : "text-slate-600 hover:bg-slate-200"}`}>
              <span className="flex-1">Tickets</span>
              {ticketsPendingCount > 0 && (
                <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-white">{ticketsPendingCount}</span>
              )}
            </button>
          )}
        </div>
        <div className="mt-2 flex items-center gap-2 px-3 py-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-600 text-xs font-semibold text-white">{(businessName ?? "?").charAt(0).toUpperCase()}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-slate-700">{businessName ?? "Account"}</p>
            <p className="truncate text-[11px] text-slate-400">{assistantName ?? "Assistant"}</p>
          </div>
          {canSignOut && (
            <button type="button" onClick={signOut} title="Sign out" aria-label="Sign out" className="rounded-md p-1.5 text-slate-400 hover:bg-slate-200">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 3H5.25A2.25 2.25 0 0 0 3 5.25v13.5A2.25 2.25 0 0 0 5.25 21H9M12 12h9m0 0-3-3m3 3-3 3" />
              </svg>
            </button>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete conversation"
        message={pendingDelete ? `"${pendingDelete.title?.trim() || "this conversation"}" will be permanently deleted. This can't be undone.` : ""}
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
