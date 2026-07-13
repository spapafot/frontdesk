import { launcherIconSvg } from "../../widget/icons";
import { contrastColor, shiftColor } from "../../widget/theme";
import type { AppearanceState } from "./WidgetAppearance";

interface Props {
  appearance: AppearanceState;
  assistantName: string;
  businessName: string;
  showBranding: boolean;
}

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

const SEND_ICON =
  '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3.4 20.4l17.45-7.48a1 1 0 0 0 0-1.84L3.4 3.6a.993.993 0 0 0-1.39.91L2 9.12c0 .5.37.93.87.99L17 12 2.87 13.88c-.5.07-.87.5-.87 1l.01 4.61c0 .71.73 1.2 1.39.91z"/></svg>';
const AVATAR_ICON =
  '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';

function Svg({ html, className }: { html: string; className?: string }) {
  return <span className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}

export function WidgetPreview({
  appearance,
  assistantName,
  businessName,
  showBranding,
}: Props) {
  const accent = HEX.test(appearance.accentColor) ? appearance.accentColor : "#0284c7";
  const strong = shiftColor(accent, -28);
  const contrast = contrastColor(accent);
  const gradient = `linear-gradient(135deg, ${accent} 0%, ${strong} 100%)`;
  const left = appearance.launcherPosition === "bottom-left";

  return (
    <div className="relative min-h-[500px] overflow-hidden rounded-2xl border border-slate-700 bg-gradient-to-br from-slate-800 to-slate-900 shadow-inner">
      {/* Fake browser chrome so it reads as a real website */}
      <div className="flex items-center gap-1.5 border-b border-white/10 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400/80" />
        <span className="h-3 w-3 rounded-full bg-amber-400/80" />
        <span className="h-3 w-3 rounded-full bg-emerald-400/80" />
        <div className="ml-3 h-5 w-40 rounded-full bg-white/10" />
      </div>
      {/* Skeleton page content */}
      <div className="space-y-3 p-6 opacity-30">
        <div className="h-6 w-2/3 rounded bg-white/25" />
        <div className="h-3 w-full rounded bg-white/15" />
        <div className="h-3 w-11/12 rounded bg-white/15" />
        <div className="h-3 w-4/5 rounded bg-white/15" />
      </div>

      {/* The widget, anchored to the chosen corner */}
      <div
        className={`absolute bottom-5 flex flex-col gap-3 ${
          left ? "left-5 items-start" : "right-5 items-end"
        }`}
      >
        {/* Chat panel */}
        <div className="flex h-[380px] w-[300px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3" style={{ background: gradient, color: contrast }}>
            <span
              className="flex h-9 w-9 flex-none items-center justify-center rounded-full [&_svg]:h-5 [&_svg]:w-5"
              style={{ background: "rgba(255,255,255,0.2)" }}
            >
              <Svg html={AVATAR_ICON} className="flex" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-bold">{assistantName || "Assistant"}</div>
              <div className="mt-0.5 flex items-center gap-1.5 text-[11px] opacity-90">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                <span className="truncate">{businessName || "Online"}</span>
              </div>
            </div>
            <span className="ml-auto opacity-80 [&_svg]:h-5 [&_svg]:w-5">
              <Svg
                html='<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>'
                className="flex"
              />
            </span>
          </div>

          {/* Messages */}
          <div className="flex flex-1 flex-col gap-2.5 overflow-hidden bg-white p-4">
            <div className="flex items-end gap-2">
              <span
                className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-slate-100 [&_svg]:h-4 [&_svg]:w-4"
                style={{ color: accent }}
              >
                <Svg html={AVATAR_ICON} className="flex" />
              </span>
              <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-slate-100 px-3 py-2 text-[13px] leading-snug text-slate-800">
                {appearance.greeting || "Hi! How can I help you today?"}
              </div>
            </div>
            <div
              className="max-w-[80%] self-end rounded-2xl rounded-br-md px-3 py-2 text-[13px] leading-snug"
              style={{ background: gradient, color: contrast }}
            >
              What are your opening hours?
            </div>
          </div>

          {/* Composer */}
          <div className="flex items-center gap-2 border-t border-slate-200 p-3">
            <div className="flex-1 rounded-full bg-slate-100 px-4 py-2 text-[13px] text-slate-400">
              Type a message…
            </div>
            <span
              className="flex h-9 w-9 flex-none items-center justify-center rounded-full [&_svg]:h-4 [&_svg]:w-4"
              style={{ background: gradient, color: contrast }}
            >
              <Svg html={SEND_ICON} className="flex" />
            </span>
          </div>

          {showBranding && (
            <div className="pb-2 pt-1 text-center text-[10px] text-slate-400">
              Powered by <span className="font-semibold">Plug &amp; Play</span>
            </div>
          )}
        </div>

        {/* Launcher */}
        <button
          type="button"
          disabled
          className="inline-flex h-14 items-center rounded-full shadow-xl"
          style={{ background: gradient, color: contrast }}
          aria-label="Launcher preview"
        >
          <span className="flex h-14 w-14 items-center justify-center [&_svg]:h-7 [&_svg]:w-7">
            <Svg html={launcherIconSvg(appearance.launcherIcon)} className="flex" />
          </span>
          {appearance.launcherLabel && (
            <span className="pr-5 text-sm font-semibold">{appearance.launcherLabel}</span>
          )}
        </button>
      </div>
    </div>
  );
}
