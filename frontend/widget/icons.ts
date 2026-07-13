// Preset launcher icons, defined once and shared by the embed loader
// (loader.ts, built as a standalone IIFE) and the admin app's appearance
// picker + live preview (WidgetAppearance.tsx / WidgetPreview.tsx). The backend
// mirrors these keys in schemas/settings.py to validate `launcher_icon`.
//
// Each SVG is a self-contained string using `fill="currentColor"`, so the
// launcher's color comes from its container's `color` and the SVG scales to
// whatever width/height the surrounding CSS sets.

export interface LauncherIcon {
  key: string;
  label: string;
  svg: string;
}

const svg = (path: string) =>
  `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${path}"/></svg>`;

export const LAUNCHER_ICONS: LauncherIcon[] = [
  {
    key: "chat",
    label: "Chat bubble",
    svg: svg("M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"),
  },
  {
    key: "chat-dots",
    label: "Chat dots",
    svg: svg(
      "M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM9 11H7V9h2v2zm4 0h-2V9h2v2zm4 0h-2V9h2v2z"
    ),
  },
  {
    key: "help",
    label: "Question",
    svg: svg(
      "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"
    ),
  },
  {
    key: "headset",
    label: "Support",
    svg: svg(
      "M12 1c-4.97 0-9 4.03-9 9v7c0 1.66 1.34 3 3 3h3v-8H5v-2c0-3.87 3.13-7 7-7s7 3.13 7 7v2h-4v8h3c1.66 0 3-1.34 3-3v-7c0-4.97-4.03-9-9-9z"
    ),
  },
  {
    key: "sparkles",
    label: "Sparkles",
    svg: svg(
      "M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z"
    ),
  },
  {
    key: "smile",
    label: "Smiley",
    svg: svg(
      "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z"
    ),
  },
];

export const DEFAULT_LAUNCHER_ICON = "chat";

const BY_KEY: Record<string, string> = Object.fromEntries(
  LAUNCHER_ICONS.map((icon) => [icon.key, icon.svg])
);

/** Resolve a preset key to its SVG markup, falling back to the default. */
export function launcherIconSvg(key: string | null | undefined): string {
  return (key && BY_KEY[key]) || BY_KEY[DEFAULT_LAUNCHER_ICON];
}
