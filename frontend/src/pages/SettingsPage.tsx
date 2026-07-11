import { FormEvent, useEffect, useState } from "react";
import useSWR from "swr";
import {
  Settings,
  getSettings,
  settingsKey,
  rotateWidgetKey,
  updateSettings,
} from "../api/settings";
import { WidgetInstall } from "../components/WidgetInstall";

export function SettingsPage() {
  const { data, error, isLoading, mutate } = useSWR<Settings>(settingsKey, getSettings);

  const [businessName, setBusinessName] = useState("");
  const [assistantName, setAssistantName] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [widgetOrigin, setWidgetOrigin] = useState("");
  const [widgetEnabled, setWidgetEnabled] = useState(true);
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
    }
  }, [data]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      const updated = await updateSettings({
        business_name: businessName.trim(),
        assistant_name: assistantName.trim(),
        custom_instructions: customInstructions,
        widget_origin: widgetOrigin,
        widget_enabled: widgetEnabled,
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
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex min-h-full max-w-2xl flex-col p-4">
      <h2 className="text-lg font-semibold text-slate-800">Settings</h2>
      <p className="mt-1 text-sm text-slate-500">
        Configure how your assistant introduces itself and how it should behave.
      </p>

      {isLoading && <p className="mt-4 text-sm text-slate-500">Loading...</p>}
      {error && <p className="mt-4 text-sm text-red-600">Failed to load settings.</p>}

      {data && (
        <form onSubmit={submit} className="mt-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700">Business name</label>
            <input
              type="text"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Assistant name</label>
            <input
              type="text"
              value={assistantName}
              onChange={(e) => setAssistantName(e.target.value)}
              required
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
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
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
            <p className="mt-1 text-right text-xs text-slate-400">
              {customInstructions.length}/4000
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="rounded-full bg-sky-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save settings"}
            </button>
            {saved && <span className="text-sm text-emerald-600">Saved.</span>}
            {saveError && <span className="text-sm text-red-600">{saveError}</span>}
          </div>

          <div className="border-t border-slate-200 pt-5">
            <label className="block text-sm font-medium text-slate-700">
              Website origin
            </label>
            <p className="text-xs text-slate-400">
              Exact HTTPS origin where the widget is installed.
            </p>
            <input
              type="url"
              value={widgetOrigin}
              onChange={(e) => setWidgetOrigin(e.target.value)}
              placeholder="https://example.com"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
            <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={widgetEnabled}
                onChange={(e) => setWidgetEnabled(e.target.checked)}
              />
              Widget enabled
            </label>
            <p className="mt-2 text-xs text-slate-500">
              {(data.widget_monthly_usage ?? 0).toLocaleString()} of{" "}
              {(data.widget_monthly_limit ?? 0).toLocaleString()} messages used this month
            </p>
          </div>
        </form>
      )}

        {data && (
          <WidgetInstall
            siteKey={data.public_key}
            onRotate={async () => {
              const updated = await rotateWidgetKey();
              await mutate(updated, { revalidate: false });
            }}
          />
        )}
      </div>
    </div>
  );
}
