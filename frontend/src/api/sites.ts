import { API_BASE } from "./client";

/** A website the admin manages: one assistant profile + its single widget. */
export interface Site {
  id: number;
  name: string;
  assistant_name: string;
  type: string;
  public_key: string | null;
  widget_origin: string | null;
  widget_enabled: boolean;
  widget_monthly_limit: number;
  widget_monthly_usage: number;
  created_at: string;
}

export const sitesKey = `${API_BASE}/sites`;

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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function listSites(): Promise<Site[]> {
  return handle(await fetch(sitesKey));
}

export async function createSite(payload: {
  name: string;
  widget_origin?: string;
}): Promise<Site> {
  return handle(
    await fetch(sitesKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}

export async function renameSite(id: number, name: string): Promise<Site> {
  return handle(
    await fetch(`${sitesKey}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    })
  );
}

export async function deleteSite(id: number): Promise<void> {
  return handle(await fetch(`${sitesKey}/${id}`, { method: "DELETE" }));
}
