import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import useSWR from "swr";
import {
  Settings,
  getSettings,
  settingsKey,
  rotateWidgetKey,
  updateSettings,
} from "../api/settings";
import { WidgetInstall } from "../components/WidgetInstall";
import { WidgetAppearance, AppearanceState } from "../components/WidgetAppearance";
import { WidgetPreview } from "../components/WidgetPreview";
import { usePlan } from "../components/PlanProvider";
import { useSite } from "../components/SiteProvider";
import { Skeleton } from "../components/Skeleton";
import { RenameWebsiteDialog } from "../components/RenameWebsiteDialog";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { TeamSection } from "../components/TeamSection";

const DEFAULT_APPEARANCE: AppearanceState = {
  accentColor: "#0284c7",
  launcherIcon: "chat",
  launcherPosition: "bottom-right",
  greeting: "Hi! How can I help you today?",
  launcherLabel: "",
};

export function SettingsPage() {
  const { selectedSiteId, sites, current, renameSite, deleteSite } = useSite();
  const { entitlements, isSuperAdmin } = usePlan();
  const navigate = useNavigate();
  // Super-admins get every plan feature regardless of subscription. Live
  // handoff additionally needs the deployment-level flag (not a plan gate).
  const canRemoveBranding = isSuperAdmin || entitlements.remove_branding;
  const canLiveHandoff = isSuperAdmin || entitlements.live_handoff;
  const { data, error, isLoading, mutate } = useSWR<Settings>(
    selectedSiteId != null ? settingsKey(selectedSiteId) : null,
    () => getSettings(selectedSiteId as number)
  );

  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const [businessName, setBusinessName] = useState("");
  const [assistantName, setAssistantName] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [widgetOrigin, setWidgetOrigin] = useState("");
  const [widgetEnabled, setWidgetEnabled] = useState(true);
  const [liveHumanEscalationEnabled, setLiveHumanEscalationEnabled] = useState(false);
  const [talkToPersonAfter, setTalkToPersonAfter] = useState("3");
  const [moderationEnabled, setModerationEnabled] = useState(true);
  const [notificationEmail, setNotificationEmail] = useState("");
  const [showBranding, setShowBranding] = useState(true);
  const [appearance, setAppearance] = useState<AppearanceState>(DEFAULT_APPEARANCE);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setBusinessName(data.business_name);
      setAssistantName(data.assistant_name);
      setCustomInstructions(data.custom_instructions ?? "");
      setWidgetOrigin(data.widget_origin ?? "");
      setWidgetEnabled(data.widget_enabled ?? true);
      setLiveHumanEscalationEnabled(data.live_human_escalation_enabled ?? false);
      setTalkToPersonAfter(String(data.talk_to_person_after ?? 3));
      setModerationEnabled(data.moderation_enabled ?? true);
      setNotificationEmail(data.notification_email ?? "");
      setShowBranding(data.show_branding ?? true);
      setAppearance({
        accentColor: data.accent_color,
        launcherIcon: data.launcher_icon,
        launcherPosition: data.launcher_position,
        greeting: data.greeting,
        launcherLabel: data.launcher_label ?? "",
      });
    }
  }, [data]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      const updated = await updateSettings(selectedSiteId as number, {
        business_name: businessName.trim(),
        assistant_name: assistantName.trim(),
        custom_instructions: customInstructions,
        widget_origin: widgetOrigin,
        widget_enabled: widgetEnabled,
        live_human_escalation_enabled: liveHumanEscalationEnabled,
        talk_to_person_after:
          talkToPersonAfter === "" ? undefined : Math.min(50, Number(talkToPersonAfter)),
        moderation_enabled: moderationEnabled,
        notification_email: notificationEmail.trim() || undefined,
        accent_color: appearance.accentColor.trim(),
        launcher_icon: appearance.launcherIcon,
        launcher_position: appearance.launcherPosition,
        greeting: appearance.greeting.trim(),
        launcher_label: appearance.launcherLabel.trim(),
        show_branding: showBranding,
      });
      await mutate(updated, { revalidate: false });
      setSaved(true);
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-5">
        <h1 className="text-lg font-semibold text-slate-900">Settings</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Configure how your assistant introduces itself, behaves, and looks on your site.
        </p>
      </header>
      <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full max-w-5xl flex-col p-6">

        {isLoading && <SettingsSkeleton />}
        {error && <p className="mt-4 text-sm text-red-600">Failed to load settings.</p>}

        {data && (
          <form onSubmit={submit} className="space-y-5">
            {/* Assistant */}
            <section className="max-w-3xl space-y-5 rounded-2xl border border-slate-200 bg-white p-5">
              <div>
                <h2 className="text-sm font-semibold text-slate-900">Assistant</h2>
                <p className="mt-0.5 text-xs text-slate-500">Set the identity and behavior used across this website.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">Business name</label>
                <input
                  type="text"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  required
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700">Assistant name</label>
                <input
                  type="text"
                  value={assistantName}
                  onChange={(e) => setAssistantName(e.target.value)}
                  required
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700">
                  Custom instructions
                </label>
                <p className="text-xs text-slate-400">
                  Extra guidance and tone for the assistant. These add to the built-in safety
                  rules and cannot override them.
                </p>
                <textarea
                  value={customInstructions}
                  onChange={(e) => setCustomInstructions(e.target.value)}
                  rows={6}
                  maxLength={4000}
                  placeholder="e.g. Always greet customers warmly. Refer to our company as 'the team'."
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
                />
                <p className="mt-1 text-right text-xs text-slate-400">
                  {customInstructions.length}/4000
                </p>
              </div>
            </section>

            {/* Widget appearance */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-800">Widget appearance</h3>
              <p className="mt-1 text-xs text-slate-500">
                Customize the chat launcher and window. The preview updates as you edit.
              </p>
              <div className="mt-5 grid gap-8 lg:grid-cols-2">
                <WidgetAppearance
                  value={appearance}
                  onChange={setAppearance}
                  showBranding={showBranding}
                  onShowBrandingChange={setShowBranding}
                  canRemoveBranding={canRemoveBranding}
                  onUpgrade={() => navigate("/billing")}
                />
                <div className="lg:sticky lg:top-4 lg:self-start">
                  <WidgetPreview
                    appearance={appearance}
                    assistantName={assistantName}
                    businessName={businessName}
                    showBranding={showBranding}
                  />
                </div>
              </div>
            </section>

            {/* Website & access */}
            <section className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-5">
              <h3 className="text-sm font-semibold text-slate-900">Website & access</h3>
              <label className="block text-sm font-medium text-slate-700">Website origin</label>
              <p className="text-xs text-slate-400">
                Exact HTTPS origin where the widget is installed.
              </p>
              <input
                type="url"
                value={widgetOrigin}
                onChange={(e) => setWidgetOrigin(e.target.value)}
                placeholder="https://example.com"
                className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
              />
              <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={widgetEnabled}
                  onChange={(e) => setWidgetEnabled(e.target.checked)}
                />
                Widget enabled
              </label>
              <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={liveHumanEscalationEnabled}
                  disabled={!data.live_human_escalation_available || !canLiveHandoff}
                  onChange={(e) => setLiveHumanEscalationEnabled(e.target.checked)}
                />
                Allow visitors to talk to a person
                {data.live_human_escalation_available && !canLiveHandoff && (
                  <button
                    type="button"
                    onClick={() => navigate("/billing")}
                    className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-medium text-sky-700 hover:bg-sky-200"
                  >
                    Upgrade
                  </button>
                )}
              </label>
              {!data.live_human_escalation_available ? (
                <p className="mt-1 text-xs text-slate-400">
                  Live support is disabled for this deployment. Enable the global flag after
                  deploying the Lambda migration and Durable Objects.
                </p>
              ) : (
                !canLiveHandoff && (
                  <p className="mt-1 text-xs text-slate-400">
                    Live human handoff is available on the Pro and Business plans.
                  </p>
                )
              )}
              <div className="mt-3">
                <label className="block text-sm font-medium text-slate-700">
                  Show &ldquo;Talk to a person&rdquo; after
                </label>
                <p className="text-xs text-slate-400">
                  Number of visitor messages before the option appears (0 = from the first
                  message). It also appears sooner if the assistant can&apos;t answer or the
                  visitor asks for a human.
                </p>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={talkToPersonAfter}
                  disabled={!data.live_human_escalation_available || !liveHumanEscalationEnabled}
                  onChange={(e) => setTalkToPersonAfter(e.target.value.replace(/\D/g, ""))}
                  maxLength={2}
                  placeholder="3"
                  className="mt-1.5 w-24 rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500 disabled:bg-slate-50 disabled:text-slate-400"
                />
              </div>
              <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={moderationEnabled}
                  disabled={!data.moderation_available}
                  onChange={(e) => setModerationEnabled(e.target.checked)}
                />
                Automatically moderate abusive visitor messages
              </label>
              <p className="mt-1 text-xs text-slate-400">
                {data.moderation_available
                  ? "Abusive messages get a warning instead of an answer; repeated abuse closes the conversation."
                  : "Moderation is unavailable for this deployment (requires an OpenAI API key)."}
              </p>
              <div className="mt-4">
                <label className="block text-sm font-medium text-slate-700">
                  Notification email
                </label>
                <p className="text-xs text-slate-400">
                  Support-request tickets are emailed here. Defaults to your login email.
                </p>
                <input
                  type="email"
                  value={notificationEmail}
                  onChange={(e) => setNotificationEmail(e.target.value)}
                  maxLength={254}
                  placeholder="support@example.com"
                  className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
                />
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {(data.widget_monthly_usage ?? 0).toLocaleString()} messages from
                this site this month · check your total quota on the{" "}
                <Link to="/billing" className="text-sky-600 hover:underline">
                  Billing page
                </Link>
              </p>
            </section>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={saving}
                className="rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save settings"}
              </button>
              {saved && <span className="text-sm text-emerald-600">Saved.</span>}
              {saveError && <span className="text-sm text-red-600">{saveError}</span>}
            </div>
          </form>
        )}

        {data && (
          <WidgetInstall
            siteKey={data.public_key}
            accentColor={data.accent_color}
            launcherIcon={data.launcher_icon}
            launcherPosition={data.launcher_position}
            greeting={data.greeting}
            launcherLabel={data.launcher_label ?? ""}
            showBranding={showBranding}
            onRotate={async () => {
              const updated = await rotateWidgetKey(selectedSiteId as number);
              await mutate(updated, { revalidate: false });
            }}
          />
        )}

        {current && (
          <section className="mt-5 max-w-3xl rounded-2xl border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold text-slate-800">Website</h3>
            <p className="mt-1 text-xs text-slate-500">
              Rename this website, or permanently delete it and everything in it.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setRenameOpen(true)}
                className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Rename website
              </button>
              {sites && sites.length > 1 && (
                <button
                  type="button"
                  onClick={() => setDeleteOpen(true)}
                  className="rounded-xl border border-red-200 bg-white px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-50"
                >
                  Delete website
                </button>
              )}
            </div>
          </section>
        )}

        <TeamSection />
      </div>
      </div>

      <RenameWebsiteDialog
        open={renameOpen}
        initialName={current?.name ?? ""}
        onClose={() => setRenameOpen(false)}
        onSubmit={async (name) => {
          if (current) await renameSite(current.id, name);
        }}
      />

      <ConfirmDialog
        open={deleteOpen}
        title="Delete website"
        message={
          current
            ? `"${current.name}" and all of its knowledge base, conversations, and widget settings will be permanently deleted. This can't be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          if (current) void deleteSite(current.id);
          setDeleteOpen(false);
        }}
        onCancel={() => setDeleteOpen(false)}
      />
    </div>
  );
}

function SettingsSkeleton() {
  return (
    <div className="mt-6 space-y-8" role="status" aria-label="Loading settings">
      <section className="max-w-2xl space-y-5">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-2 h-10 w-full rounded-lg" />
          </div>
        ))}
        <div>
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-2 h-28 w-full rounded-lg" />
        </div>
      </section>

      <section className="border-t border-slate-200 pt-6">
        <Skeleton className="h-4 w-44" />
        <div className="mt-5 grid gap-8 lg:grid-cols-2">
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-lg" />
            ))}
          </div>
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
      </section>

      <div>
        <Skeleton className="h-10 w-36 rounded-full" />
      </div>
    </div>
  );
}
