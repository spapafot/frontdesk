import { useState } from "react";
import useSWR from "swr";
import { analyticsKey, getAnalytics } from "../api/analytics";
import {
  conversationsKey,
  ConversationSummary,
  getConversationDetail,
  getConversationMessages,
  listConversations,
  StoredMessage,
} from "../api/conversations";
import { useSite } from "../components/SiteProvider";
import { Skeleton } from "../components/Skeleton";

interface Props {
  onOpenConversation: (id: number) => void;
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

function ratingBadge(rating: string | null) {
  if (rating === "up")
    return <span className="text-xs font-medium text-emerald-600">Helpful</span>;
  if (rating === "down")
    return <span className="text-xs font-medium text-red-600">Not helpful</span>;
  return <span className="text-xs text-slate-400">-</span>;
}

function MetricCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-2xl font-semibold text-slate-800">{value}</p>
      <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  );
}

export function AnalyticsPage({ onOpenConversation }: Props) {
  const { selectedSiteId } = useSite();
  const { data: analytics, isLoading } = useSWR(
    selectedSiteId != null ? analyticsKey(selectedSiteId) : null,
    () => getAnalytics(selectedSiteId as number)
  );
  const { data: conversations } = useSWR(
    selectedSiteId != null ? conversationsKey(selectedSiteId) : null,
    () => listConversations(selectedSiteId as number)
  );

  const [transcript, setTranscript] = useState<StoredMessage[] | null>(null);
  const [detail, setDetail] = useState<ConversationSummary | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const openTranscript = async (id: number) => {
    if (selectedSiteId == null) return;
    setLoadingDetail(true);
    setTranscript([]);
    try {
      const [messages, conversationDetail] = await Promise.all([
        getConversationMessages(selectedSiteId, id),
        getConversationDetail(selectedSiteId, id),
      ]);
      setTranscript(messages);
      setDetail(conversationDetail);
    } finally {
      setLoadingDetail(false);
    }
  };

  const closeTranscript = () => {
    setTranscript(null);
    setDetail(null);
  };

  return (
    <div className="mx-auto h-full max-w-4xl overflow-y-auto p-4">
      <h2 className="text-lg font-semibold text-slate-800">Logs & analytics</h2>
      <p className="mt-1 text-sm text-slate-500">
        Conversation volume, customer ratings, and questions the assistant could not answer.
      </p>

      {isLoading && <AnalyticsSkeleton />}

      {analytics && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MetricCard label="Conversations" value={analytics.total_conversations} />
            <MetricCard label="Last 7 days" value={analytics.last_7_days} />
            <MetricCard label="Helpful" value={analytics.ratings.up} />
            <MetricCard label="Not helpful" value={analytics.ratings.down} />
          </div>

          <section className="mt-8">
            <h3 className="text-sm font-semibold text-slate-700">
              Unanswered questions ({analytics.unanswered.length})
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Questions where the assistant searched but found nothing - candidates for new
              knowledge base content.
            </p>
            <div className="mt-3 space-y-2">
              {analytics.unanswered.length === 0 && (
                <p className="text-sm text-slate-400">No unanswered questions. Nice.</p>
              )}
              {analytics.unanswered.map((item, idx) => (
                <div
                  key={`${item.conversation_id}-${idx}`}
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm text-slate-700">{item.question}</p>
                    <p className="text-[11px] text-slate-400">
                      {formatTime(item.created_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onOpenConversation(item.conversation_id)}
                    className="ml-3 shrink-0 text-xs font-medium text-sky-600 hover:underline"
                  >
                    Open chat
                  </button>
                </div>
              ))}
            </div>
          </section>

          <section className="mt-8">
            <h3 className="text-sm font-semibold text-slate-700">Recent conversations</h3>
            <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full min-w-[32rem] border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 text-left text-xs uppercase text-slate-400">
                    <th className="px-3 py-2">Conversation</th>
                    <th className="px-3 py-2">Started</th>
                    <th className="px-3 py-2">Rating</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {conversations === undefined &&
                    Array.from({ length: 4 }).map((_, i) => (
                      <tr key={`skeleton-${i}`} className="border-t border-slate-100">
                        <td className="px-3 py-2">
                          <Skeleton className="h-4 w-40" />
                        </td>
                        <td className="px-3 py-2">
                          <Skeleton className="h-4 w-24" />
                        </td>
                        <td className="px-3 py-2">
                          <Skeleton className="h-4 w-16" />
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex justify-end">
                            <Skeleton className="h-4 w-10" />
                          </div>
                        </td>
                      </tr>
                    ))}
                  {conversations?.map((c) => (
                    <tr key={c.id} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-medium text-slate-800">
                        <span className="line-clamp-1">{c.title ?? "Conversation"}</span>
                      </td>
                      <td className="px-3 py-2 text-slate-500">
                        {formatTime(c.started_at)}
                      </td>
                      <td className="px-3 py-2">{ratingBadge(c.rating)}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => openTranscript(c.id)}
                          className="text-xs font-medium text-sky-600 hover:underline"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                  {conversations && conversations.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-center text-slate-400">
                        No conversations yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {transcript !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
          onClick={closeTranscript}
          role="presentation"
        >
          <div
            className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-xl bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="border-b border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-800">Transcript</h3>
              {loadingDetail && <Skeleton className="mt-2 h-3 w-3/4" />}
              {detail?.summary && (
                <p className="mt-1 text-xs text-slate-500">{detail.summary}</p>
              )}
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {loadingDetail &&
                transcript.length === 0 &&
                [
                  { w: "w-1/2", side: "justify-end" },
                  { w: "w-2/3", side: "justify-start" },
                  { w: "w-1/3", side: "justify-end" },
                ].map((b, idx) => (
                  <div key={`skeleton-${idx}`} className={`flex ${b.side}`}>
                    <Skeleton className={`h-10 ${b.w} rounded-lg`} />
                  </div>
                ))}
              {transcript.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                      m.role === "user"
                        ? "bg-sky-600 text-white"
                        : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {m.content}
                  </div>
                </div>
              ))}
            </div>
            <div className="border-t border-slate-200 p-3 text-right">
              <button
                type="button"
                onClick={closeTranscript}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="mt-4" role="status" aria-label="Loading analytics">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-xl border border-slate-200 bg-white p-4">
            <Skeleton className="h-8 w-12" />
            <Skeleton className="mt-2 h-3 w-20" />
          </div>
        ))}
      </div>

      <section className="mt-8">
        <Skeleton className="h-4 w-48" />
        <div className="mt-3 space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="mt-1 h-3 w-24" />
              </div>
              <Skeleton className="ml-3 h-4 w-16" />
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <Skeleton className="h-4 w-40" />
        <div className="mt-3 space-y-2 rounded-lg border border-slate-200 p-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      </section>
    </div>
  );
}
