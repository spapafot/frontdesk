import { API_BASE } from "./client";

export interface Settings {
  business_name: string;
  assistant_name: string;
  custom_instructions: string | null;
  public_key: string | null;
  widget_origin: string | null;
  widget_enabled: boolean;
  widget_monthly_limit: number;
  widget_monthly_usage: number;
  widget_resets_at: string;
}

export const settingsKey = `${API_BASE}/settings`;

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

export async function getSettings(): Promise<Settings> {
  return handle(await fetch(settingsKey));
}

export async function updateSettings(payload: {
  business_name: string;
  assistant_name: string;
  custom_instructions: string;
  widget_origin: string;
  widget_enabled: boolean;
}): Promise<Settings> {
  return handle(
    await fetch(settingsKey, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function rotateWidgetKey(): Promise<Settings> {
  return handle(await fetch(`${settingsKey}/widget-key/rotate`, { method: "POST" }));
}
