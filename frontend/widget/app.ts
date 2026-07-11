// Dependency-free chat UI rendered inside the widget iframe. Chat-only over SSE
// Keep the embeddable widget bundle as small as possible.

interface Params {
  token: string;
  installation: string;
  origin: string;
  assistant: string;
  business: string;
  api: string;
  accent: string;
  greeting: string;
}

function readParams(): Params {
  const q = new URLSearchParams(location.hash.slice(1));
  return {
    token: q.get("token") || "",
    installation: q.get("installation") || "",
    origin: q.get("origin") || "",
    assistant: q.get("assistant") || "Chat",
    business: q.get("business") || "",
    api: (q.get("api") || "").replace(/\/$/, ""),
    accent: q.get("accent") || "#0284c7",
    greeting: q.get("greeting") || "Hi! How can I help you today?",
  };
}

const params = readParams();
history.replaceState(null, "", `${location.pathname}${location.search}`);
document.documentElement.style.setProperty("--accent", params.accent);

const app = document.getElementById("app") as HTMLDivElement;
let conversationId: number | null = null;
const convStorageKey = `wx_conv_${params.installation}_${encodeURIComponent(params.origin)}`;
const stored = Number(localStorage.getItem(convStorageKey));
if (Number.isFinite(stored) && stored > 0) conversationId = stored;

let streaming = false;
let widgetToken = params.token;
let refreshResolver: ((token: string | null) => void) | null = null;

window.addEventListener("message", (event) => {
  if (
    event.origin === params.origin &&
    event.source === parent &&
    event.data?.type === "wx-session"
  ) {
    refreshResolver?.(event.data.token || null);
    refreshResolver = null;
  }
});

function refreshToken(): Promise<string | null> {
  return new Promise((resolve) => {
    refreshResolver = resolve;
    parent.postMessage({ type: "wx-refresh" }, params.origin);
    setTimeout(() => {
      if (refreshResolver === resolve) {
        refreshResolver = null;
        resolve(null);
      }
    }, 10000);
  });
}

app.innerHTML = `
  <header class="wx-header">
    <div>
      <h1 id="wx-title">Chat</h1>
      <p id="wx-subtitle"></p>
    </div>
    <button class="wx-close" id="wx-close" title="Close" aria-label="Close">&times;</button>
  </header>
  <div class="wx-messages" id="wx-messages"></div>
  <form class="wx-form" id="wx-form">
    <input class="wx-input" id="wx-input" type="text" placeholder="Type a message..." autocomplete="off" />
    <button class="wx-send" id="wx-send" type="submit">Send</button>
  </form>
`;

const titleEl = document.getElementById("wx-title") as HTMLElement;
const subtitleEl = document.getElementById("wx-subtitle") as HTMLElement;
const messagesEl = document.getElementById("wx-messages") as HTMLDivElement;
const formEl = document.getElementById("wx-form") as HTMLFormElement;
const inputEl = document.getElementById("wx-input") as HTMLInputElement;
const sendEl = document.getElementById("wx-send") as HTMLButtonElement;

document.getElementById("wx-close")?.addEventListener("click", () => {
  parent.postMessage({ type: "wx-close" }, params.origin);
});

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

async function loadConfig() {
  if (!params.token) {
    titleEl.textContent = "Configuration error";
    subtitleEl.textContent = "Missing site key";
    return;
  }
  titleEl.textContent = params.assistant;
  subtitleEl.textContent = params.business;
}

function setStreaming(value: boolean) {
  streaming = value;
  sendEl.disabled = value;
  inputEl.disabled = value;
}

async function send(text: string) {
  const trimmed = text.trim();
  if (!trimmed || streaming) return;
  addBubble("user", trimmed);
  inputEl.value = "";
  setStreaming(true);

  const pending = addBubble("assistant", "");
  pending.classList.add("pending");
  let answer = "";

  try {
    const request = () => fetch(`${params.api}/chat/stream`, {
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
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, sep).trim();
        buffer = buffer.slice(sep + 2);
        if (!raw.startsWith("data:")) continue;
        const json = raw.slice(raw.indexOf("data:") + 5).trim();
        if (!json) continue;
        let evt: Record<string, unknown>;
        try {
          evt = JSON.parse(json);
        } catch {
          continue;
        }
        switch (evt.type) {
          case "conversation":
            conversationId = evt.conversation_id as number;
            localStorage.setItem(convStorageKey, String(conversationId));
            break;
          case "token":
            answer += evt.content as string;
            pending.classList.remove("pending");
            pending.textContent = answer;
            scrollToBottom();
            break;
          case "error":
            pending.classList.remove("pending");
            pending.classList.add("wx-error");
            pending.textContent = (evt.message as string) || "Something went wrong.";
            break;
        }
      }
    }
    if (!answer && !pending.classList.contains("wx-error")) {
      pending.classList.remove("pending");
      pending.textContent = "(no response)";
    }
  } catch (err) {
    pending.classList.remove("pending");
    pending.classList.add("wx-error");
    pending.textContent = (err as Error).message || "Connection error.";
  } finally {
    setStreaming(false);
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  void send(inputEl.value);
});

void loadConfig();
addBubble("assistant", params.greeting);
inputEl.focus();
