import { FormEvent, useEffect, useState } from "react";
import useSWR from "swr";
import {
  Settings,
  SPEED_OPTIONS,
  VOICE_OPTIONS,
  getSettings,
  settingsKey,
  updateSettings,
} from "../api/settings";

export function SettingsPage() {
  const { data, error, isLoading, mutate } = useSWR<Settings>(settingsKey, getSettings);

  const [businessName, setBusinessName] = useState("");
  const [assistantName, setAssistantName] = useState("");
  const [customInstructions, setCustomInstructions] = useState("");
  const [ttsVoice, setTtsVoice] = useState("nova");
  const [ttsSpeed, setTtsSpeed] = useState(1.1);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setBusinessName(data.business_name);
      setAssistantName(data.assistant_name);
      setCustomInstructions(data.custom_instructions ?? "");
      setTtsVoice(data.tts_voice);
      setTtsSpeed(data.tts_speed);
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
        tts_voice: ttsVoice,
        tts_speed: ttsSpeed,
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
    <div className="mx-auto flex h-full max-w-2xl flex-col overflow-y-auto p-4">
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

          <div>
            <label className="block text-sm font-medium text-slate-700">Voice</label>
            <p className="text-xs text-slate-400">
              The voice used for spoken replies and the "Play" button.
            </p>
            <select
              value={ttsVoice}
              onChange={(e) => setTtsVoice(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {VOICE_OPTIONS.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">
              Speaking speed
            </label>
            <p className="text-xs text-slate-400">How fast spoken replies are played.</p>
            <select
              value={ttsSpeed}
              onChange={(e) => setTtsSpeed(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {SPEED_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
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
        </form>
      )}
    </div>
  );
}
