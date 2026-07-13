// Dependency-free chat UI rendered inside the widget iframe. Chat-only over SSE.

import { contrastColor, shiftColor } from "./theme";

interface Params {
  origin: string;
  api: string;
  accent: string;
  greeting: string;
  turnstileSiteKey: string;
  branding: boolean;
}

interface WidgetSession {
  token: string;
  installation_id: number;
  origin: string;
  assistant_name: string;
  business_name: string;
}

interface TurnstileApi {
  render(
    container: string | HTMLElement,
    options: {
      sitekey: string;
      action: string;
      theme: "auto";
      size: "flexible";
      callback: (token: string) => void;
      "error-callback": () => void;
      "expired-callback": () => void;
      "timeout-callback": () => void;
    },
  ): string;
  reset(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

// Where "Powered by Plug & Play" links to. Kept in one place for easy change.
const POWERED_BY_URL = "https://plugandplay.gr";

function readParams(): Params {
  const q = new URLSearchParams(location.hash.slice(1));
  return {
    origin: q.get("origin") || "",
    api: (q.get("api") || "").replace(/\/$/, ""),
    accent: q.get("accent") || "#0284c7",
    greeting: q.get("greeting") || "Hi! How can I help you today?",
    turnstileSiteKey: q.get("turnstileSiteKey") || "",
    branding: q.get("branding") !== "false",
  };
}

const params = readParams();
history.replaceState(null, "", `${location.pathname}${location.search}`);
const rootStyle = document.documentElement.style;
rootStyle.setProperty("--accent", params.accent);
rootStyle.setProperty("--accent-strong", shiftColor(params.accent, -28));
rootStyle.setProperty("--accent-contrast", contrastColor(params.accent));

const AVATAR_ICON =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>';
const SEND_ICON =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3.4 20.4l17.45-7.48a1 1 0 0 0 0-1.84L3.4 3.6a.993.993 0 0 0-1.39.91L2 9.12c0 .5.37.93.87.99L17 12 2.87 13.88c-.5.07-.87.5-.87 1l.01 4.61c0 .71.73 1.2 1.39.91z"/></svg>';
const TYPING =
  '<span class="wx-typing"><span></span><span></span><span></span></span>';

const app = document.getElementById("app") as HTMLDivElement;
app.innerHTML = `
  <header class="wx-header">
    <div class="wx-header-main">
      <div class="wx-avatar wx-avatar-lg">${AVATAR_ICON}</div>
      <div class="wx-header-text">
        <h1 id="wx-title">Chat</h1>
        <div class="wx-status"><span class="wx-dot"></span><span id="wx-subtitle">Online</span></div>
      </div>
    </div>
    <button class="wx-close" id="wx-close" title="Minimize" aria-label="Minimize chat">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>
    </button>
  </header>
  <section class="wx-verification" id="wx-verification" aria-live="polite">
    <div class="wx-spinner" aria-hidden="true"></div>
    <p id="wx-verification-message">Securing chat&hellip;</p>
    <div id="wx-turnstile"></div>
    <button class="wx-retry" id="wx-retry" type="button" hidden>Try again</button>
  </section>
  <div class="wx-messages" id="wx-messages" role="log" aria-live="polite" hidden></div>
  <form class="wx-form" id="wx-form" hidden>
    <input class="wx-input" id="wx-input" type="text" placeholder="Type a message&hellip;" autocomplete="off" />
    <button class="wx-send" id="wx-send" type="submit" aria-label="Send message">${SEND_ICON}</button>
  </form>
  <div class="wx-footer" id="wx-branding"${params.branding ? "" : " hidden"}>
    Powered by <a href="${POWERED_BY_URL}" target="_blank" rel="noopener noreferrer">Plug &amp; Play</a>
  </div>
`;

const titleEl = document.getElementById("wx-title") as HTMLElement;
const subtitleEl = document.getElementById("wx-subtitle") as HTMLElement;
const verificationEl = document.getElementById(
  "wx-verification",
) as HTMLElement;
const verificationMessageEl = document.getElementById(
  "wx-verification-message",
) as HTMLElement;
const retryEl = document.getElementById("wx-retry") as HTMLButtonElement;
const messagesEl = document.getElementById("wx-messages") as HTMLDivElement;
const formEl = document.getElementById("wx-form") as HTMLFormElement;
const inputEl = document.getElementById("wx-input") as HTMLInputElement;
const sendEl = document.getElementById("wx-send") as HTMLButtonElement;

let conversationId: number | null = null;
let conversationStorageKey = "";
let streaming = false;
let widgetToken = "";
let turnstileWidgetId: string | null = null;
let refreshResolver: ((token: string | null) => void) | null = null;
let chatInitialized = false;

function postToParent(message: object) {
  if (params.origin) parent.postMessage(message, params.origin);
}

function showVerificationError(
  message = "Verification failed. Please try again.",
) {
  verificationEl.hidden = false;
  messagesEl.hidden = true;
  formEl.hidden = true;
  verificationMessageEl.textContent = message;
  verificationMessageEl.classList.add("wx-error");
  retryEl.hidden = false;
}

function showChat(session: WidgetSession) {
  widgetToken = session.token;
  titleEl.textContent = session.assistant_name || "Chat";
  subtitleEl.textContent = session.business_name || "Online";
  conversationStorageKey = `wx_conv_${session.installation_id}_${encodeURIComponent(session.origin)}`;
  const stored = Number(localStorage.getItem(conversationStorageKey));
  conversationId = Number.isFinite(stored) && stored > 0 ? stored : null;
  verificationEl.hidden = true;
  messagesEl.hidden = false;
  formEl.hidden = false;
  if (!chatInitialized) {
    chatInitialized = true;
    addBubble("assistant", params.greeting);
  }
  refreshResolver?.(session.token);
  refreshResolver = null;
  inputEl.focus();
}

function renderVerification() {
  retryEl.hidden = true;
  verificationMessageEl.classList.remove("wx-error");
  verificationMessageEl.textContent = "Securing chat…";
  verificationEl.hidden = false;
  messagesEl.hidden = true;
  formEl.hidden = true;

  // Local development can run without Turnstile. Production enforcement at
  // the Worker/backend still rejects an empty token, so this cannot fail open.
  if (!params.turnstileSiteKey) {
    postToParent({ type: "wx-turnstile", token: "" });
    return;
  }
  if (!window.turnstile) {
    showVerificationError(
      "Verification could not load. Check your connection and retry.",
    );
    return;
  }
  if (turnstileWidgetId) {
    window.turnstile.reset(turnstileWidgetId);
    return;
  }
  turnstileWidgetId = window.turnstile.render("#wx-turnstile", {
    sitekey: params.turnstileSiteKey,
    action: "widget-session",
    theme: "auto",
    size: "flexible",
    callback: (token) => {
      verificationMessageEl.textContent = "Finishing verification…";
      postToParent({ type: "wx-turnstile", token });
    },
    "error-callback": () => showVerificationError(),
    "expired-callback": () =>
      showVerificationError("Verification expired. Please try again."),
    "timeout-callback": () =>
      showVerificationError("Verification timed out. Please try again."),
  });
}

window.addEventListener("message", (event) => {
  if (event.origin !== params.origin || event.source !== parent) return;
  if (event.data?.type === "wx-session" && event.data.session?.token) {
    showChat(event.data.session as WidgetSession);
  } else if (event.data?.type === "wx-verification-error") {
    showVerificationError();
    refreshResolver?.(null);
    refreshResolver = null;
  } else if (event.data?.type === "wx-verify") {
    renderVerification();
  }
});

document.getElementById("wx-close")?.addEventListener("click", () => {
  postToParent({ type: "wx-close" });
});
retryEl.addEventListener("click", renderVerification);

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addBubble(role: "user" | "assistant", text: string): HTMLDivElement {
  const bubble = document.createElement("div");
  bubble.className = `wx-bubble ${role}`;
  bubble.textContent = text;

  if (role === "assistant") {
    const row = document.createElement("div");
    row.className = "wx-row assistant";
    const avatar = document.createElement("div");
    avatar.className = "wx-avatar";
    avatar.innerHTML = AVATAR_ICON;
    row.appendChild(avatar);
    row.appendChild(bubble);
    messagesEl.appendChild(row);
  } else {
    messagesEl.appendChild(bubble);
  }
  scrollToBottom();
  return bubble;
}

function setStreaming(value: boolean) {
  streaming = value;
  sendEl.disabled = value;
  inputEl.disabled = value;
}

function refreshToken(): Promise<string | null> {
  return new Promise((resolve) => {
    refreshResolver = resolve;
    postToParent({ type: "wx-refresh" });
    setTimeout(() => {
      if (refreshResolver === resolve) {
        refreshResolver = null;
        resolve(null);
      }
    }, 120000);
  });
}

async function send(text: string) {
  const trimmed = text.trim();
  if (!trimmed || streaming || !widgetToken) return;
  addBubble("user", trimmed);
  inputEl.value = "";
  setStreaming(true);

  const pending = addBubble("assistant", "");
  pending.classList.add("pending");
  pending.innerHTML = TYPING;
  let answer = "";

  try {
    const request = () =>
      fetch(`${params.api}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          conversation_id: conversationId,
          widget_token: widgetToken,
        }),
      });
    let res = await request();
    if (res.status === 401) {
      const refreshed = await refreshToken();
      if (refreshed) {
        widgetToken = refreshed;
        res = await request();
      }
    }
    if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separator: number;
      while ((separator = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, separator).trim();
        buffer = buffer.slice(separator + 2);
        if (!raw.startsWith("data:")) continue;
        const json = raw.slice(raw.indexOf("data:") + 5).trim();
        if (!json) continue;
        let event: Record<string, unknown>;
        try {
          event = JSON.parse(json);
        } catch {
          continue;
        }
        switch (event.type) {
          case "conversation":
            conversationId = event.conversation_id as number;
            if (conversationStorageKey) {
              localStorage.setItem(
                conversationStorageKey,
                String(conversationId),
              );
            }
            break;
          case "token":
            answer += event.content as string;
            pending.classList.remove("pending");
            pending.textContent = answer;
            scrollToBottom();
            break;
          case "error":
            pending.classList.remove("pending");
            pending.classList.add("wx-error");
            pending.textContent =
              (event.message as string) || "Something went wrong.";
            break;
        }
      }
    }
    if (!answer && !pending.classList.contains("wx-error")) {
      pending.classList.remove("pending");
      pending.textContent = "(no response)";
    }
  } catch (error) {
    pending.classList.remove("pending");
    pending.classList.add("wx-error");
    pending.textContent = (error as Error).message || "Connection error.";
  } finally {
    setStreaming(false);
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  void send(inputEl.value);
});

window.addEventListener("load", renderVerification, { once: true });

export {};
