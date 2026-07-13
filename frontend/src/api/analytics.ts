import { API_BASE } from "./client";

export interface RatingBreakdown {
  up: number;
  down: number;
  none: number;
}

export interface UnansweredQuestion {
  conversation_id: number;
  question: string;
  created_at: string;
}

export interface Analytics {
  total_conversations: number;
  last_7_days: number;
  ratings: RatingBreakdown;
  unanswered: UnansweredQuestion[];
}

export const analyticsKey = (siteId: number) => `${API_BASE}/analytics?site_id=${siteId}`;

export async function getAnalytics(siteId: number): Promise<Analytics> {
  const response = await fetch(analyticsKey(siteId));
  if (!response.ok) throw new Error(`Failed to load analytics (${response.status})`);
  return (await response.json()) as Analytics;
}
