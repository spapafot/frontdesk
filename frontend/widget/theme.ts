// Accent-color helpers shared by the embed loader (launcher styling) and the
// iframe app (chat UI theming). The accent is customer-chosen, so we derive a
// readable text color and a darker shade rather than hard-coding white-on-accent.

export function parseHex(hex: string): [number, number, number] | null {
  let h = (hex || "").trim().replace(/^#/, "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (!/^[0-9a-fA-F]{6}$/.test(h)) return null;
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

/** Black or white text, whichever is more readable on the given accent. */
export function contrastColor(hex: string): string {
  const rgb = parseHex(hex);
  if (!rgb) return "#ffffff";
  const [r, g, b] = rgb;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.62 ? "#0f172a" : "#ffffff";
}

/** Lighten (positive) or darken (negative) a hex color by `amount` per channel. */
export function shiftColor(hex: string, amount: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));
  const shifted = rgb.map((c) => clamp(c + amount)) as [number, number, number];
  return `#${shifted.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}
