// Embeddable loader (built as a standalone IIFE). The customer drops a single
// <script> tag; this injects a floating launcher button and, on click, an
// <iframe> that hosts the chat UI. A Shadow DOM isolates the launcher from the
// host page's CSS, and the iframe isolates the chat app entirely.

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

  // Derive default URLs from where this script is served, unless overridden.
  const scriptUrl = new URL(current.src, location.href);
  const apiBase = (ds.api || scriptUrl.origin).replace(/\/$/, "");
  const appUrl = ds.app || new URL("./app/index.html", scriptUrl).href;

  if (!siteKey) {
    console.error("[chat-widget] missing data-site-key");
    return;
  }

  const host = document.createElement("div");
  host.style.cssText = "position:fixed;z-index:2147483000;";
  const root = host.attachShadow({ mode: "open" });
  document.body.appendChild(host);

  const side = position === "bottom-left" ? "left:20px;" : "right:20px;";

  const style = document.createElement("style");
  style.textContent = `
    .launcher {
      position: fixed; bottom: 20px; ${side}
      width: 56px; height: 56px; border-radius: 50%;
      background: ${accent}; color: #fff; border: 0; cursor: pointer;
      box-shadow: 0 6px 20px rgba(0,0,0,.25);
      display: flex; align-items: center; justify-content: center;
      transition: transform .15s ease;
    }
    .launcher:hover { transform: scale(1.05); }
    .launcher svg { width: 26px; height: 26px; fill: currentColor; }
    .frame-wrap {
      position: fixed; bottom: 88px; ${side}
      width: 380px; height: 560px; max-width: calc(100vw - 40px);
      max-height: calc(100vh - 120px);
      border-radius: 16px; overflow: hidden; background: #fff;
      box-shadow: 0 12px 40px rgba(0,0,0,.28);
      display: none;
    }
    .frame-wrap.open { display: block; }
    iframe { width: 100%; height: 100%; border: 0; }
    @media (max-width: 480px) {
      .frame-wrap {
        bottom: 0; right: 0; left: 0; width: 100vw; height: 100vh;
        max-width: 100vw; max-height: 100vh; border-radius: 0;
      }
    }
  `;
  root.appendChild(style);

  const wrap = document.createElement("div");
  wrap.className = "frame-wrap";

  const iframe = document.createElement("iframe");
  iframe.title = "Chat";
  iframe.allow = "clipboard-write";
  const src = new URL(appUrl);
  // Defer setting iframe.src until first open to avoid loading until needed.

  const launcher = document.createElement("button");
  launcher.className = "launcher";
  launcher.setAttribute("aria-label", "Open chat");
  const chatIcon =
    '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';
  const closeIcon =
    '<svg viewBox="0 0 24 24"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';
  launcher.innerHTML = chatIcon;

  let open = false;
  let loaded = false;
  async function createSession() {
    const body = new URLSearchParams({ key: siteKey });
    const response = await fetch(`${apiBase}/widget/session`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!response.ok) throw new Error(`Widget authorization failed (${response.status})`);
    return await response.json();
  }

  async function loadFrame() {
    const session = await createSession();
    src.hash = new URLSearchParams({
      token: session.token,
      installation: String(session.installation_id),
      origin: session.origin,
      assistant: session.assistant_name,
      business: session.business_name,
      api: apiBase,
      accent,
      greeting,
    }).toString();
    iframe.src = src.href;
  }

  async function setOpen(next: boolean) {
    open = next;
    wrap.classList.toggle("open", open);
    launcher.innerHTML = open ? closeIcon : chatIcon;
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
      e.data?.type === "wx-refresh"
    ) {
      try {
        const session = await createSession();
        iframe.contentWindow?.postMessage(
          { type: "wx-session", token: session.token },
          src.origin
        );
      } catch {
        iframe.contentWindow?.postMessage(
          { type: "wx-session", token: null },
          src.origin
        );
      }
    }
  });

  wrap.appendChild(iframe);
  root.appendChild(wrap);
  root.appendChild(launcher);
})();
