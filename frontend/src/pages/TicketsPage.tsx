import { CallbackTicket } from "../api/live";
import { Skeleton } from "../components/Skeleton";

interface Props {
  callbacks: CallbackTicket[] | undefined;
  onResolve: (id: number) => void | Promise<void>;
}

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

function TicketCard({
  ticket,
  onResolve,
}: {
  ticket: CallbackTicket;
  onResolve?: (id: number) => void | Promise<void>;
}) {
  const pending = ticket.status === "pending";
  return (
    <div
      className={`rounded-xl border px-4 py-3 ${
        pending ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className={`text-sm font-medium ${pending ? "text-amber-950" : "text-slate-700"}`}>
          {ticket.customer_name?.trim() || ticket.customer_email}
        </p>
        <span className="text-xs text-slate-500">{ticket.customer_email}</span>
        <button
          type="button"
          className={`text-xs font-semibold underline ${pending ? "text-amber-900" : "text-slate-500"}`}
          onClick={() => void navigator.clipboard.writeText(ticket.customer_email)}
        >
          Copy email
        </button>
        <span className="ml-auto text-[11px] text-slate-400">
          {pending
            ? formatTime(ticket.created_at)
            : `Resolved ${ticket.resolved_at ? formatTime(ticket.resolved_at) : ""}`}
        </span>
      </div>
      {ticket.customer_message?.trim() && (
        <p className={`mt-2 whitespace-pre-wrap text-sm ${pending ? "text-amber-900" : "text-slate-500"}`}>
          {ticket.customer_message}
        </p>
      )}
      {pending && onResolve && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => void onResolve(ticket.id)}
            className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100"
          >
            Resolve
          </button>
        </div>
      )}
    </div>
  );
}

export function TicketsPage({ callbacks, onResolve }: Props) {
  const pending = callbacks?.filter((item) => item.status === "pending") ?? [];
  const resolved = callbacks?.filter((item) => item.status === "resolved") ?? [];

  return (
    <div className="mx-auto h-full max-w-4xl overflow-y-auto p-4">
      <h2 className="text-lg font-semibold text-slate-800">Tickets</h2>
      <p className="mt-1 text-sm text-slate-500">
        Visitors who asked for help while no one was available. New tickets are also sent to
        your notification email.
      </p>

      {callbacks === undefined && (
        <div className="mt-4 space-y-2" role="status" aria-label="Loading tickets">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      )}

      {callbacks !== undefined && callbacks.length === 0 && (
        <p className="mt-6 text-sm text-slate-400">No tickets yet.</p>
      )}

      {pending.length > 0 && (
        <section className="mt-4">
          <h3 className="text-sm font-semibold text-slate-700">Pending ({pending.length})</h3>
          <div className="mt-2 space-y-2">
            {pending.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} onResolve={onResolve} />
            ))}
          </div>
        </section>
      )}

      {resolved.length > 0 && (
        <section className="mt-6">
          <h3 className="text-sm font-semibold text-slate-700">Resolved ({resolved.length})</h3>
          <div className="mt-2 space-y-2">
            {resolved.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
