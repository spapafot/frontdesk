// Embeddable loader (built as a standalone IIFE). The customer drops a single
// <script> tag; this injects a floating launcher button and, on click, an
// <iframe> that hosts the chat UI. A Shadow DOM isolates the launcher from the
// host page's CSS, and the iframe isolates the chat app entirely.

import { launcherIconSvg } from "./icons";
import { contrastColor, shiftColor } from "./theme";

(function () {
  const current =
    (document.currentScript as HTMLScriptElement | null) ||
    (function () {
      const scripts = document.getElementsByTagName("script");
      return scripts[scripts.length - 1] as HTMLScriptElement;
    })();

  if (!current) return;

  const ds = current.dataset;
  const siteKey = ds.siteKey || "";
  const accent = ds.accent || "#0284c7";
  const position = ds.position === "bottom-left" ? "bottom-left" : "bottom-right";
  const greeting = ds.greeting || "Hi! How can I help you today?";
  const iconKey = ds.icon || "chat";
  const launcherLabel = (ds.launcherLabel || "").trim();
  const branding = ds.branding !== "false";
  const turnstileSiteKey =
    ds.turnstileSiteKey || import.meta.env.VITE_TURNSTILE_SITE_KEY || "";

  // Derive default URLs from where this script is served, unless overridden.
  const scriptUrl = new URL(current.src, location.href);
  const apiBase = (ds.api || scriptUrl.origin).replace(/\/$/, "");
  const appUrl = ds.app || new URL("./app/index.html", scriptUrl).href;

  if (!siteKey) {
    console.error("[chat-widget] missing data-site-key");
    return;
  }

  const accentStrong = shiftColor(accent, -28);
  const accentContrast = contrastColor(accent);

  const host = document.createElement("div");
  host.style.cssText = "position:fixed;z-index:2147483000;";
  const root = host.attachShadow({ mode: "open" });
  document.body.appendChild(host);

  const side = position === "bottom-left" ? "left:20px;" : "right:20px;";

  const style = document.createElement("style");
  style.textContent = `
    .launcher {
      position: fixed; bottom: 20px; ${side}
      height: 56px; min-width: 56px;
      border-radius: 999px;
      background: linear-gradient(135deg, ${accent} 0%, ${accentStrong} 100%);
      color: ${accentContrast}; border: 0; cursor: pointer;
      box-shadow: 0 8px 24px rgba(0,0,0,.22);
      display: inline-flex; align-items: center; padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      transition: transform .18s ease, box-shadow .18s ease;
      animation: launcher-in .32s cubic-bezier(.2,.8,.2,1);
    }
    .launcher:hover { transform: translateY(-2px) scale(1.03); box-shadow: 0 12px 30px rgba(0,0,0,.28); }
    .launcher:active { transform: scale(.97); }
    .launcher-icon {
      display: flex; align-items: center; justify-content: center;
      width: 56px; height: 56px; flex: none;
    }
    .launcher-icon svg { width: 26px; height: 26px; fill: currentColor; transition: transform .2s ease; }
    .launcher-label {
      display: none; white-space: nowrap; font-size: 15px; font-weight: 600;
      padding-right: 22px; padding-left: 2px;
    }
    .launcher.has-label:not(.open) .launcher-label { display: block; }
    .launcher.has-label:not(.open) .launcher-icon { width: 48px; padding-left: 8px; }
    @keyframes launcher-in {
      from { opacity: 0; transform: scale(.6) translateY(8px); }
      to { opacity: 1; transform: scale(1) translateY(0); }
    }
    .frame-wrap {
      position: fixed; bottom: 90px; ${side}
      width: 384px; height: 620px; max-width: calc(100vw - 40px);
      max-height: calc(100vh - 120px);
      border-radius: 18px; overflow: hidden; background: #fff;
      box-shadow: 0 16px 48px rgba(0,0,0,.24);
      opacity: 0; transform: translateY(16px) scale(.98);
      transform-origin: bottom ${position === "bottom-left" ? "left" : "right"};
      transition: opacity .2s ease, transform .2s cubic-bezier(.2,.8,.2,1);
      pointer-events: none;
    }
    .frame-wrap.open { display: block; opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
    iframe { width: 100%; height: 100%; border: 0; display: block; }
    @media (max-width: 480px) {
      .frame-wrap {
        bottom: 0; right: 0; left: 0; width: 100vw; height: 100dvh;
        max-width: 100vw; max-height: 100dvh; border-radius: 0;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .launcher, .frame-wrap, .launcher-icon svg { animation: none; transition: none; }
    }
  `;
  root.appendChild(style);

  const wrap = document.createElement("div");
  wrap.className = "frame-wrap";
  // Hidden until first open; toggled via the `.open` class.
  wrap.style.display = "none";

  const iframe = document.createElement("iframe");
  iframe.title = "Chat";
  iframe.allow = "clipboard-write";
  const src = new URL(appUrl);
  // Defer setting iframe.src until first open to avoid loading until needed.

  const launcher = document.createElement("button");
  launcher.className = launcherLabel ? "launcher has-label" : "launcher";
  launcher.setAttribute("aria-label", "Open chat");
  const iconSvg = launcherIconSvg(iconKey);
  const closeIcon =
    '<svg viewBox="0 0 24 24"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
  const renderLauncher = (isOpen: boolean) => {
    const label = launcherLabel
      ? `<span class="launcher-label">${escapeHtml(launcherLabel)}</span>`
      : "";
    launcher.innerHTML = `<span class="launcher-icon">${isOpen ? closeIcon : iconSvg}</span>${isOpen ? "" : label}`;
  };
  renderLauncher(false);

  let open = false;
  let loaded = false;
  async function createSession(turnstileToken: string) {
    const body = new URLSearchParams({
      key: siteKey,
      turnstile_token: turnstileToken,
    });
    const response = await fetch(`${apiBase}/widget/session`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!response.ok) throw new Error(`Widget authorization failed (${response.status})`);
    return await response.json();
  }

  async function loadFrame() {
    src.hash = new URLSearchParams({
      origin: location.origin,
      api: apiBase,
      accent,
      greeting,
      turnstileSiteKey,
      branding: branding ? "true" : "false",
    }).toString();
    iframe.src = src.href;
  }

  async function setOpen(next: boolean) {
    open = next;
    if (open) wrap.style.display = "block";
    // Allow the display change to apply before toggling the animated class.
    requestAnimationFrame(() => wrap.classList.toggle("open", open));
    launcher.classList.toggle("open", open);
    renderLauncher(open);
    launcher.setAttribute("aria-label", open ? "Close chat" : "Open chat");
    if (open && !loaded) {
      loaded = true;
      try {
        await loadFrame();
      } catch (error) {
        loaded = false;
        console.error("[chat-widget]", error);
        setOpen(false);
      }
    }
  }

  launcher.addEventListener("click", () => setOpen(!open));
  window.addEventListener("message", async (e) => {
    if (
      e.origin === src.origin &&
      e.source === iframe.contentWindow &&
      e.data?.type === "wx-close"
    ) {
      setOpen(false);
    } else if (
      e.origin === src.origin &&
      e.source === iframe.contentWindow &&
      e.data?.type === "wx-turnstile" &&
      typeof e.data.token === "string"
    ) {
      try {
        const session = await createSession(e.data.token);
        iframe.contentWindow?.postMessage(
          { type: "wx-session", session },
          src.origin
        );
      } catch (error) {
        iframe.contentWindow?.postMessage(
          { type: "wx-verification-error" },
          src.origin
        );
        console.error("[chat-widget]", error);
      }
    } else if (
      e.origin === src.origin &&
      e.source === iframe.contentWindow &&
      e.data?.type === "wx-refresh"
    ) {
      iframe.contentWindow?.postMessage({ type: "wx-verify" }, src.origin);
    }
  });

  function escapeHtml(value: string): string {
    return value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  wrap.appendChild(iframe);
  root.appendChild(wrap);
  root.appendChild(launcher);
})();
