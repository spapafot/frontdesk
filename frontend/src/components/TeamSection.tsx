import { FormEvent, useState } from "react";
import useSWR from "swr";
import {
  TeamMember,
  inviteTeamMember,
  listTeamMembers,
  removeTeamMember,
  teamKey,
} from "../api/team";
import { ConfirmDialog } from "./ConfirmDialog";

/**
 * Owner-only team management, rendered on the Settings page. Invited members
 * get access to every site on this account: tickets, live chats, history,
 * knowledge base, and analytics - everything except settings and this list.
 */
export function TeamSection() {
  const { data: members, error, mutate } = useSWR(teamKey, listTeamMembers);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingRemove, setPendingRemove] = useState<TeamMember | null>(null);

  const onInvite = async (e: FormEvent) => {
    e.preventDefault();
    const value = email.trim();
    if (!value || busy) return;
    setBusy(true);
    setInviteError(null);
    setNotice(null);
    try {
      const result = await inviteTeamMember(value);
      await mutate((list) => [...(list ?? []), result.member], {
        revalidate: false,
      });
      setEmail("");
      setNotice(result.detail ?? `Invitation sent to ${result.member.email}.`);
    } catch (err) {
      setInviteError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const onRemove = async (member: TeamMember) => {
    try {
      await mutate(
        async (list) => {
          await removeTeamMember(member.id);
          return list?.filter((m) => m.id !== member.id) ?? [];
        },
        {
          optimisticData: (list) =>
            list?.filter((m) => m.id !== member.id) ?? [],
          rollbackOnError: true,
          revalidate: false,
        },
      );
    } catch {
      setNotice(null);
      setInviteError("Couldn't remove the team member. Restored.");
    }
  };

  return (
    <section className="mt-5 max-w-3xl rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-slate-800">Team</h3>
      <p className="mt-1 text-xs text-slate-500">
        Invite people to help you answer tickets and live chats. Members get
        access to all of your websites, but can't change settings or manage the
        team.
      </p>

      <form onSubmit={onInvite} className="mt-4 flex gap-2">
        <label htmlFor="team-invite-email" className="sr-only">
          Email address to invite
        </label>
        <input
          id="team-invite-email"
          type="email"
          required
          maxLength={254}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="colleague@example.com"
          className="min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
        />
        <button
          type="submit"
          disabled={busy}
          className="shrink-0 rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
        >
          {busy ? "Inviting…" : "Send invite"}
        </button>
      </form>
      {inviteError && (
        <p className="mt-2 text-sm text-red-600">{inviteError}</p>
      )}
      {notice && (
        <p className="mt-2 text-sm text-sky-700" role="status">
          {notice}
        </p>
      )}

      <div className="mt-4">
        {error && (
          <p className="text-sm text-red-600">Failed to load your team.</p>
        )}
        {members && members.length === 0 && (
          <p className="text-sm text-slate-500">
            No team members yet. Invite your first one above.
          </p>
        )}
        {members && members.length > 0 && (
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-slate-50/50">
            {members.map((member) => (
              <li
                key={member.id}
                className="flex items-center gap-3 px-4 py-2.5"
              >
                <span className="min-w-0 flex-1 truncate text-sm text-slate-700">
                  {member.email}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    member.status === "active"
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {member.status === "active" ? "Active" : "Invited"}
                </span>
                <button
                  type="button"
                  onClick={() => setPendingRemove(member)}
                  className="text-xs font-medium text-red-600 hover:underline"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingRemove !== null}
        title="Remove team member"
        message={
          pendingRemove
            ? `${pendingRemove.email} will immediately lose access to all of your websites.`
            : ""
        }
        confirmLabel="Remove"
        destructive
        onConfirm={() => {
          if (pendingRemove) void onRemove(pendingRemove);
          setPendingRemove(null);
        }}
        onCancel={() => setPendingRemove(null)}
      />
    </section>
  );
}
