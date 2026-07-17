import { API_BASE } from "./client";

export type LauncherPosition = "bottom-right" | "bottom-left";

export interface Settings {
  business_name: string;
  assistant_name: string;
  custom_instructions: string | null;
  public_key: string | null;
  widget_origin: string | null;
  widget_enabled: boolean;
  widget_monthly_usage: number;
  widget_resets_at: string;
  // Appearance
  accent_color: string;
  launcher_icon: string;
  launcher_position: LauncherPosition;
  greeting: string;
  launcher_label: string | null;
  show_branding: boolean;
  live_human_escalation_enabled: boolean;
  live_human_escalation_available: boolean;
  moderation_enabled: boolean;
  moderation_available: boolean;
  notification_email: string | null;
  talk_to_person_after: number;
}

export const settingsKey = (siteId: number) => `${API_BASE}/settings?site_id=${siteId}`;

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function getSettings(siteId: number): Promise<Settings> {
  return handle(await fetch(settingsKey(siteId)));
}

export async function updateSettings(
  siteId: number,
  payload: {
    business_name: string;
    assistant_name: string;
    custom_instructions: string;
    widget_origin: string;
    widget_enabled: boolean;
    live_human_escalation_enabled: boolean;
    moderation_enabled: boolean;
    // Omitted (undefined) when empty: the backend rejects a blank email and
    // treats an absent field as "leave unchanged".
    notification_email?: string;
    // Omitted (undefined) when the input is left blank.
    talk_to_person_after?: number;
    accent_color: string;
    launcher_icon: string;
    launcher_position: LauncherPosition;
    greeting: string;
    launcher_label: string;
    show_branding: boolean;
  }
): Promise<Settings> {
  return handle(
    await fetch(settingsKey(siteId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function rotateWidgetKey(siteId: number): Promise<Settings> {
  return handle(
    await fetch(`${API_BASE}/settings/widget-key/rotate?site_id=${siteId}`, {
      method: "POST",
    })
  );
}
