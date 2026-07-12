// Dependency-free chat UI rendered inside the widget iframe. Chat-only over SSE.

interface Params {
  origin: string;
  api: string;
  accent: string;
  greeting: string;
  turnstileSiteKey: string;
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
    }
  ): string;
  reset(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

function readParams(): Params {
  const q = new URLSearchParams(location.hash.slice(1));
  return {
    origin: q.get("origin") || "",
    api: (q.get("api") || "").replace(/\/$/, ""),
    accent: q.get("accent") || "#0284c7",
    greeting: q.get("greeting") || "Hi! How can I help you today?",
    turnstileSiteKey: q.get("turnstileSiteKey") || "",
  };
}

const params = readParams();
history.replaceState(null, "", `${location.pathname}${location.search}`);
document.documentElement.style.setProperty("--accent", params.accent);

const app = document.getElementById("app") as HTMLDivElement;
app.innerHTML = `
  <header class="wx-header">
    <div>
      <h1 id="wx-title">Chat</h1>
      <p id="wx-subtitle"></p>
    </div>
    <button class="wx-close" id="wx-close" title="Close" aria-label="Close">&times;</button>
  </header>
  <section class="wx-verification" id="wx-verification" aria-live="polite">
    <p id="wx-verification-message">Securing chat&hellip;</p>
    <div id="wx-turnstile"></div>
    <button class="wx-retry" id="wx-retry" type="button" hidden>Try again</button>
  </section>
  <div class="wx-messages" id="wx-messages" hidden></div>
  <form class="wx-form" id="wx-form" hidden>
    <input class="wx-input" id="wx-input" type="text" placeholder="Type a message..." autocomplete="off" />
    <button class="wx-send" id="wx-send" type="submit">Send</button>
  </form>
`;

const titleEl = document.getElementById("wx-title") as HTMLElement;
const subtitleEl = document.getElementById("wx-subtitle") as HTMLElement;
const verificationEl = document.getElementById("wx-verification") as HTMLElement;
const verificationMessageEl = document.getElementById("wx-verification-message") as HTMLElement;
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

function showVerificationError(message = "Verification failed. Please try again.") {
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
  subtitleEl.textContent = session.business_name || "";
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
    showVerificationError("Verification could not load. Check your connection and retry.");
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
    "expired-callback": () => showVerificationError("Verification expired. Please try again."),
    "timeout-callback": () => showVerificationError("Verification timed out. Please try again."),
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
  const el = document.createElement("div");
  el.className = `wx-bubble ${role}`;
  el.textContent = text;
  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
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
              localStorage.setItem(conversationStorageKey, String(conversationId));
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
            pending.textContent = (event.message as string) || "Something went wrong.";
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
