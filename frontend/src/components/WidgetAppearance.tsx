import { LAUNCHER_ICONS } from "../../widget/icons";
import type { LauncherPosition } from "../api/settings";

export interface AppearanceState {
  accentColor: string;
  launcherIcon: string;
  launcherPosition: LauncherPosition;
  greeting: string;
  launcherLabel: string;
}

interface Props {
  value: AppearanceState;
  onChange: (next: AppearanceState) => void;
  // Whether the "Powered by" line is shown in the widget.
  showBranding: boolean;
  onShowBrandingChange: (next: boolean) => void;
  // Plan entitlement: removing branding is a paid-plan feature.
  canRemoveBranding: boolean;
  onUpgrade: () => void;
}

const SWATCHES = [
  "#0284c7",
  "#4f46e5",
  "#059669",
  "#db2777",
  "#d97706",
  "#7c3aed",
  "#0f172a",
];

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

export function WidgetAppearance({
  value,
  onChange,
  showBranding,
  onShowBrandingChange,
  canRemoveBranding,
  onUpgrade,
}: Props) {
  const set = (patch: Partial<AppearanceState>) =>
    onChange({ ...value, ...patch });

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-slate-700">
          Accent color
        </label>
        <p className="text-xs text-slate-400">
          Used for the launcher, header, and message bubbles.
        </p>
        <div className="mt-2 flex items-center gap-2">
          <input
            type="color"
            aria-label="Accent color"
            value={HEX.test(value.accentColor) ? value.accentColor : "#0284c7"}
            onChange={(e) => set({ accentColor: e.target.value })}
            className="h-9 w-10 cursor-pointer rounded border border-slate-300 bg-white p-0.5"
          />
          <input
            type="text"
            aria-label="Accent hex"
            value={value.accentColor}
            onChange={(e) => set({ accentColor: e.target.value })}
            className={`w-28 rounded-xl border px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-sky-500 ${
              HEX.test(value.accentColor)
                ? "border-slate-300 focus:border-sky-500"
                : "border-red-400 focus:border-red-500"
            }`}
          />
          <div className="flex flex-wrap gap-1.5">
            {SWATCHES.map((color) => (
              <button
                key={color}
                type="button"
                aria-label={`Use ${color}`}
                onClick={() => set({ accentColor: color })}
                style={{ background: color }}
                className={`h-7 w-7 rounded-full ring-offset-2 transition ${
                  value.accentColor.toLowerCase() === color
                    ? "ring-2 ring-slate-400"
                    : "hover:ring-2 hover:ring-slate-200"
                }`}
              />
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">
          Launcher icon
        </label>
        <p className="text-xs text-slate-400">
          The button shown on your website.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {LAUNCHER_ICONS.map((icon) => {
            const selected = value.launcherIcon === icon.key;
            return (
              <button
                key={icon.key}
                type="button"
                title={icon.label}
                aria-label={icon.label}
                aria-pressed={selected}
                onClick={() => set({ launcherIcon: icon.key })}
                className={`flex h-11 w-11 items-center justify-center rounded-xl border transition ${
                  selected
                    ? "border-sky-500 bg-sky-50 text-sky-600 ring-2 ring-sky-100"
                    : "border-slate-200 text-slate-500 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <span
                  className="block h-6 w-6 [&_svg]:h-6 [&_svg]:w-6"
                  dangerouslySetInnerHTML={{ __html: icon.svg }}
                />
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">
          Position
        </label>
        <div className="mt-2 inline-flex rounded-lg border border-slate-200 p-1">
          {(["bottom-right", "bottom-left"] as LauncherPosition[]).map(
            (pos) => (
              <button
                key={pos}
                type="button"
                onClick={() => set({ launcherPosition: pos })}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  value.launcherPosition === pos
                    ? "bg-sky-600 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {pos === "bottom-right" ? "Bottom right" : "Bottom left"}
              </button>
            ),
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">
          Greeting message
        </label>
        <p className="text-xs text-slate-400">
          The first message visitors see.
        </p>
        <input
          type="text"
          value={value.greeting}
          maxLength={500}
          onChange={(e) => set({ greeting: e.target.value })}
          className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">
          Launcher label{" "}
          <span className="font-normal text-slate-400">(optional)</span>
        </label>
        <p className="text-xs text-slate-400">
          Short text shown beside the button, e.g. "Chat with us". Leave empty
          for an icon only.
        </p>
        <input
          type="text"
          value={value.launcherLabel}
          maxLength={60}
          placeholder="Chat with us"
          onChange={(e) => set({ launcherLabel: e.target.value })}
          className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
        />
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <label className="flex items-start gap-3 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={!showBranding}
            disabled={!canRemoveBranding}
            onChange={(e) => onShowBrandingChange(!e.target.checked)}
            className="mt-0.5"
          />
          <span>
            <span className="font-medium text-slate-700">
              Remove "Powered by Plug &amp; Play" branding
            </span>
            {!canRemoveBranding && (
              <button
                type="button"
                onClick={onUpgrade}
                className="ml-2 rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-medium text-sky-700 hover:bg-sky-200"
              >
                Upgrade to enable
              </button>
            )}
            <span className="mt-0.5 block text-xs text-slate-400">
              {canRemoveBranding
                ? "Hides the branding line at the bottom of your widget."
                : "Available on the Pro and Business plans."}
            </span>
          </span>
        </label>
      </div>
    </div>
  );
}
