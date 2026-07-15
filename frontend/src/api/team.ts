import { API_BASE } from "./client";

export interface TeamMember {
  id: number;
  email: string;
  status: "invited" | "active";
  created_at: string;
  activated_at: string | null;
}

/** Invite response. In production the edge Worker strips the email payload;
 *  only the row + human-readable feedback reach the browser. */
export interface InviteResult {
  member: TeamMember;
  already_registered: boolean;
  detail: string | null;
}

export const teamKey = `${API_BASE}/team/members`;

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

export async function listTeamMembers(): Promise<TeamMember[]> {
  return handle(await fetch(teamKey));
}

export async function inviteTeamMember(email: string): Promise<InviteResult> {
  return handle(
    await fetch(teamKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    })
  );
}

export async function removeTeamMember(id: number): Promise<void> {
  return handle(await fetch(`${teamKey}/${id}`, { method: "DELETE" }));
}
