import { DragEvent, useState } from "react";
import { Check, ChevronRight, Copy } from "lucide-react";
import { CallbackTicket, Operator, TicketStatus } from "../api/live";
import { Skeleton } from "../components/Skeleton";

interface Props {
  callbacks: CallbackTicket[] | undefined;
  operators: Operator[] | undefined;
  isOwner: boolean;
  currentUserId: string | null;
  onMove: (id: number, status: TicketStatus) => void | Promise<void>;
  onAssign: (id: number, userId: string | null) => void | Promise<void>;
  onSetArchived: (id: number, archived: boolean) => void | Promise<void>;
}

const COLUMNS: { status: TicketStatus; title: string; pill: string; dot: string }[] = [
  {
    status: "pending",
    title: "New",
    pill: "bg-amber-100 text-amber-700",
    dot: "bg-amber-400",
  },
  {
    status: "in_progress",
    title: "In progress",
    pill: "bg-sky-100 text-sky-700",
    dot: "bg-sky-500",
  },
  {
    status: "resolved",
    title: "Resolved",
    pill: "bg-emerald-100 text-emerald-700",
    dot: "bg-emerald-500",
  },
];

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function timeAgo(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const minutes = Math.round((Date.now() - date.getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function operatorLabel(operator: Operator): string {
  return operator.email ?? (operator.is_owner ? "Owner" : "Member");
}

function assigneeLabel(ticket: CallbackTicket, operators: Operator[] | undefined): string {
  if (!ticket.assignee_user_id) return "Unassigned";
  const match = operators?.find((o) => o.user_id === ticket.assignee_user_id);
  // No match means the assignee left the team since being assigned.
  return match ? operatorLabel(match) : "Former member";
}

const cardButton =
  "inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-50";
const primaryCardButton =
  "inline-flex items-center gap-1 rounded-full bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-sky-700";

function AssigneePicker({
  ticket,
  operators,
  currentUserId,
  onAssign,
}: {
  ticket: CallbackTicket;
  operators: Operator[] | undefined;
  currentUserId: string | null;
  onAssign: Props["onAssign"];
}) {
  const [open, setOpen] = useState(false);
  const label = assigneeLabel(ticket, operators);
  const chip = `inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${
    ticket.assignee_user_id
      ? "border-slate-200 bg-slate-100 text-slate-700"
      : "border-slate-200 bg-white text-slate-400"
  }`;

  // Solo account: the owner is the only possible assignee, so a picker would
  // be a dropdown with one entry. Auto-assign on "Start" covers assignment.
  if (!operators || operators.length <= 1) {
    return (
      <span className={chip} title="Assignee">
        {label}
      </span>
    );
  }

  return (
    <div className="relative min-w-0">
      <button
        type="button"
        aria-label={`Assignee: ${label}`}
        onClick={() => setOpen((v) => !v)}
        className={`${chip} transition hover:bg-slate-200`}
      >
        <span className="truncate">{label}</span>
        <svg width="10" height="10" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path
            d="M6 8l4 4 4-4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {open && (
        <>
          {/* Click-away scrim. */}
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} role="presentation" />
          <div className="absolute left-0 z-40 mt-1 w-56 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
            <ul className="max-h-64 overflow-y-auto">
              <li>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    if (ticket.assignee_user_id !== null) void onAssign(ticket.id, null);
                  }}
                  className="block w-full truncate px-3 py-2 text-left text-sm text-slate-500 transition hover:bg-slate-100"
                >
                  Unassigned
                </button>
              </li>
              {operators.map((operator) => (
                <li key={operator.user_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      if (ticket.assignee_user_id !== operator.user_id) {
                        void onAssign(ticket.id, operator.user_id);
                      }
                    }}
                    className={`block w-full truncate px-3 py-2 text-left text-sm transition ${
                      ticket.assignee_user_id === operator.user_id
                        ? "font-semibold text-sky-700"
                        : "text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {operatorLabel(operator)}
                    {operator.user_id === currentUserId && " (you)"}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}

function TicketCard({
  ticket,
  operators,
  isOwner,
  currentUserId,
  onMove,
  onAssign,
  onSetArchived,
}: {
  ticket: CallbackTicket;
} & Omit<Props, "callbacks">) {
  const timestamp =
    ticket.status === "resolved" && ticket.resolved_at ? ticket.resolved_at : ticket.created_at;

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(ticket.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      className="cursor-grab rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow-md active:cursor-grabbing"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="min-w-0 truncate text-sm font-semibold text-slate-900">
          {ticket.customer_name?.trim() || ticket.customer_email}
        </p>
        <span
          className="shrink-0 text-[11px] text-slate-400"
          title={formatTime(timestamp)}
        >
          {timeAgo(timestamp)}
        </span>
      </div>

      <div className="mt-1 flex items-center gap-1.5">
        <span className="min-w-0 truncate text-xs text-slate-500">{ticket.customer_email}</span>
        <button
          type="button"
          aria-label={`Copy ${ticket.customer_email}`}
          title="Copy email"
          className="shrink-0 rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          onClick={() => void navigator.clipboard.writeText(ticket.customer_email)}
        >
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>

      {ticket.customer_message?.trim() && (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-5 text-slate-600 line-clamp-3">
          {ticket.customer_message}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <AssigneePicker
          ticket={ticket}
          operators={operators}
          currentUserId={currentUserId}
          onAssign={onAssign}
        />
        <div className="flex shrink-0 gap-1.5">
          {ticket.status === "pending" && (
            <button type="button" className={primaryCardButton} onClick={() => void onMove(ticket.id, "in_progress")}>
              Start
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
          {ticket.status === "in_progress" && (
            <button type="button" className={primaryCardButton} onClick={() => void onMove(ticket.id, "resolved")}>
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
              Resolve
            </button>
          )}
          {ticket.status === "resolved" && (
            <>
              <button type="button" className={cardButton} onClick={() => void onMove(ticket.id, "in_progress")}>
                Reopen
              </button>
              {isOwner && (
                <button type="button" className={cardButton} onClick={() => void onSetArchived(ticket.id, true)}>
                  Archive
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function BoardColumn({
  title,
  status,
  pill,
  dot,
  tickets,
  onDropTicket,
  ...cardProps
}: {
  title: string;
  status: TicketStatus;
  pill: string;
  dot: string;
  tickets: CallbackTicket[];
  onDropTicket: (id: number, status: TicketStatus) => void;
} & Omit<Props, "callbacks">) {
  const [over, setOver] = useState(false);

  return (
    <section
      aria-label={title}
      onDragOver={(e: DragEvent) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e: DragEvent) => {
        e.preventDefault();
        setOver(false);
        const id = Number(e.dataTransfer.getData("text/plain"));
        if (Number.isInteger(id) && id > 0) onDropTicket(id, status);
      }}
      className={`flex min-h-[18rem] flex-col rounded-2xl border p-3 transition ${
        over
          ? "border-sky-300 bg-sky-50/70 ring-2 ring-sky-200"
          : "border-slate-200 bg-slate-100/80"
      }`}
    >
      <div className="flex items-center gap-2 px-1 pb-3 pt-1">
        <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${pill}`}>
          {tickets.length}
        </span>
      </div>
      <div className="flex-1 space-y-3">
        {tickets.map((ticket) => (
          <TicketCard key={ticket.id} ticket={ticket} {...cardProps} />
        ))}
        {tickets.length === 0 && (
          <div className="flex min-h-28 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white/50 px-4 text-center">
            <p className="text-xs text-slate-400">No tickets</p>
          </div>
        )}
      </div>
    </section>
  );
}

export function TicketsPage({ callbacks, ...rest }: Props) {
  const { isOwner, onMove, onSetArchived } = rest;
  const [showArchived, setShowArchived] = useState(false);

  const active = callbacks?.filter((t) => !t.archived) ?? [];
  const archived = callbacks?.filter((t) => t.archived) ?? [];

  const onDropTicket = (id: number, status: TicketStatus) => {
    const ticket = callbacks?.find((t) => t.id === id);
    if (ticket && !ticket.archived && ticket.status !== status) void onMove(id, status);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-5">
        <h1 className="text-lg font-semibold text-slate-900">Tickets</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Visitors who asked for help while no one was available. New tickets are also sent to
          your notification email.
        </p>
      </header>
      <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-7xl">

      {callbacks === undefined && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3" role="status" aria-label="Loading tickets">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-40 w-full rounded-xl" />
          ))}
        </div>
      )}

      {callbacks !== undefined && (
        <>
          <div className="grid grid-cols-1 items-start gap-5 md:grid-cols-3">
            {COLUMNS.map((column) => (
              <BoardColumn
                key={column.status}
                title={column.title}
                status={column.status}
                pill={column.pill}
                dot={column.dot}
                tickets={active.filter((t) => t.status === column.status)}
                onDropTicket={onDropTicket}
                {...rest}
              />
            ))}
          </div>

          {archived.length > 0 && (
            <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-4">
              <button
                type="button"
                onClick={() => setShowArchived((v) => !v)}
                className="flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-slate-800"
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden="true"
                  className={`transition-transform ${showArchived ? "rotate-90" : ""}`}
                >
                  <path
                    d="M8 6l4 4-4 4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Archived ({archived.length})
              </button>

              {showArchived && (
                <ul className="mt-2 space-y-1.5">
                  {archived.map((ticket) => (
                    <li
                      key={ticket.id}
                      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl bg-slate-50 px-3 py-2.5"
                    >
                      <span className="min-w-0 truncate text-sm text-slate-600">
                        {ticket.customer_name?.trim() || ticket.customer_email}
                      </span>
                      <span className="text-xs text-slate-400">{ticket.customer_email}</span>
                      <span className="ml-auto text-[11px] text-slate-400">
                        {ticket.resolved_at ? `Resolved ${formatTime(ticket.resolved_at)}` : ""}
                      </span>
                      {isOwner && (
                        <button
                          type="button"
                          className={cardButton}
                          onClick={() => void onSetArchived(ticket.id, false)}
                        >
                          Unarchive
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
      </div>
      </div>
    </div>
  );
}
