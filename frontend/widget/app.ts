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
  live_human_escalation_enabled: boolean;
}

type LiveMode = "ai" | "waiting" | "human" | "pending_ticket" | "closed";
type Rating = "up" | "down";

interface TurnstileApi {
  render(
    container: string | HTMLElement,
    options: {
      sitekey: string;
      action: string;
      theme: "auto";
      size: "flexible";
      "refresh-expired": "never";
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
const HEADSET_ICON =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 14a8 8 0 0 1 16 0"/><path d="M18 19c0 1.1-.9 2-2 2h-3"/><path d="M4 14v3a2 2 0 0 0 2 2h1v-7H6a2 2 0 0 0-2 2Z"/><path d="M20 14v3a2 2 0 0 1-2 2h-1v-7h1a2 2 0 0 1 2 2Z"/></svg>';
// Thumb glyph shared with the dashboard's RatingControl; the "down" button
// rotates it 180deg via CSS so both directions stay pixel-identical.
const THUMB_ICON =
  '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M2 21h2c.55 0 1-.45 1-1v-9c0-.55-.45-1-1-1H2v11zm19.83-7.12c.11-.25.17-.52.17-.8V11c0-1.1-.9-2-2-2h-5.5l.92-4.65c.05-.22.02-.46-.08-.66a4.8 4.8 0 0 0-.88-1.17L14 2 7.59 8.41C7.21 8.79 7 9.3 7 9.83v7.84A2.34 2.34 0 0 0 9.34 20h8.11c.7 0 1.36-.37 1.72-.97l2.66-5.15z"/></svg>';
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
  <div class="wx-live-actions" id="wx-live-actions" hidden>
    <p id="wx-live-prompt">Need more help?</p>
    <button class="wx-talk" type="button" id="wx-talk">
      <span class="wx-talk-icon">${HEADSET_ICON}</span>
      <span id="wx-talk-label">Talk to a person</span>
    </button>
    <div class="wx-rating" id="wx-rating" hidden>
      <span class="wx-rating-prompt" id="wx-rating-prompt">How was this conversation?</span>
      <div class="wx-rating-buttons">
        <button class="wx-rate" type="button" id="wx-rate-up" title="Helpful" aria-label="Helpful">${THUMB_ICON}</button>
        <button class="wx-rate wx-rate-down" type="button" id="wx-rate-down" title="Not helpful" aria-label="Not helpful">${THUMB_ICON}</button>
      </div>
    </div>
    <button type="button" id="wx-new-chat" hidden>Start a new conversation</button>
  </div>
  <form class="wx-callback" id="wx-callback" hidden>
    <p>No one is available right now. Leave your email and the team can follow up.</p>
    <input id="wx-callback-name" maxlength="120" placeholder="Name (optional)" />
    <input id="wx-callback-email" type="email" maxlength="254" required placeholder="Email" />
    <textarea id="wx-callback-message" maxlength="4000" placeholder="How can we help? (optional)"></textarea>
    <button type="submit">Request a callback</button>
  </form>
  <form class="wx-form" id="wx-form" hidden>
    <input class="wx-input" id="wx-input" type="text" placeholder="Type a message&hellip;" autocomplete="off" />
    <button class="wx-send" id="wx-send" type="submit" aria-label="Send message">${SEND_ICON}</button>
  </form>
  <div class="wx-footer" id="wx-branding"${params.branding ? "" : " hidden"}>
    <img src="./logo-icon-full-color-16.png" alt="" width="12" height="12" />
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
const liveActionsEl = document.getElementById("wx-live-actions") as HTMLDivElement;
const livePromptEl = document.getElementById("wx-live-prompt") as HTMLParagraphElement;
const talkEl = document.getElementById("wx-talk") as HTMLButtonElement;
const talkLabelEl = document.getElementById("wx-talk-label") as HTMLSpanElement;
const newChatEl = document.getElementById("wx-new-chat") as HTMLButtonElement;
const ratingEl = document.getElementById("wx-rating") as HTMLDivElement;
const ratingPromptEl = document.getElementById("wx-rating-prompt") as HTMLSpanElement;
const rateUpEl = document.getElementById("wx-rate-up") as HTMLButtonElement;
const rateDownEl = document.getElementById("wx-rate-down") as HTMLButtonElement;
const callbackEl = document.getElementById("wx-callback") as HTMLFormElement;
const callbackNameEl = document.getElementById("wx-callback-name") as HTMLInputElement;
const callbackEmailEl = document.getElementById("wx-callback-email") as HTMLInputElement;
const callbackMessageEl = document.getElementById("wx-callback-message") as HTMLTextAreaElement;

let conversationId: number | null = null;
let conversationStorageKey = "";
let conversationTokenStorageKey = "";
let visitorMessageCountStorageKey = "";
let conversationRatingStorageKey = "";
let conversationToken = "";
let visitorMessageCount = 0;
let conversationRated: Rating | "" = "";
let ratingDismissed = false;
let streaming = false;
let widgetToken = "";
let turnstileWidgetId: string | null = null;
let refreshResolver: ((token: string | null) => void) | null = null;
let chatInitialized = false;
let liveEnabled = false;
let liveMode: LiveMode = "ai";
let liveSocket: WebSocket | null = null;
let liveConnectionPromise: Promise<WebSocket> | null = null;
let handoffPromise: Promise<void> | null = null;
let connectingToHuman = false;
let connectionStatusBubble: HTMLDivElement | null = null;
let pendingHandoffResult: {
  resolve: (mode: LiveMode) => void;
  reject: (error: Error) => void;
  timer: number;
} | null = null;
let activeStream: AbortController | null = null;
let hydrateLiveHistory = false;
const displayedLiveMessageIds = new Set<number>();

// Typing indicator: while composing, refresh the outbound signal at most every
// TYPING_REFRESH_MS; the inbound indicator hides after TYPING_EXPIRE_MS without
// a refresh so a lost "stopped typing" event can never strand the dots.
const TYPING_REFRESH_MS = 2000;
const TYPING_EXPIRE_MS = 5000;
let typingSent = false;
let typingSentAt = 0;
let operatorTypingRow: HTMLElement | null = null;
let operatorTypingTimer = 0;

function postToParent(message: object) {
  if (params.origin) parent.postMessage(message, params.origin);
}

function showVerificationError(
  message = "Verification failed. Please try again.",
) {
  verificationEl.hidden = false;
  messagesEl.hidden = true;
  formEl.hidden = true;
  liveActionsEl.hidden = true;
  callbackEl.hidden = true;
  verificationMessageEl.textContent = message;
  verificationMessageEl.classList.add("wx-error");
  retryEl.hidden = false;
}

function showChat(session: WidgetSession) {
  widgetToken = session.token;
  if (chatInitialized && refreshResolver) {
    refreshResolver(session.token);
    refreshResolver = null;
    // A mid-session wx-verify hid the chat behind the verification pane;
    // bring it back now that the fresh session is here. setLiveMode restores
    // the mode-driven panels (composer, live actions, callback form).
    verificationEl.hidden = true;
    messagesEl.hidden = false;
    setLiveMode(liveMode);
    return;
  }
  titleEl.textContent = session.assistant_name || "Chat";
  subtitleEl.textContent = session.business_name || "Online";
  conversationStorageKey = `wx_conv_${session.installation_id}_${encodeURIComponent(session.origin)}`;
  conversationTokenStorageKey = `${conversationStorageKey}_token`;
  visitorMessageCountStorageKey = `${conversationStorageKey}_visitor_count`;
  conversationRatingStorageKey = `${conversationStorageKey}_rating`;
  const stored = Number(localStorage.getItem(conversationStorageKey));
  conversationId = Number.isFinite(stored) && stored > 0 ? stored : null;
  conversationToken = localStorage.getItem(conversationTokenStorageKey) || "";
  if (conversationId && !conversationToken) {
    conversationId = null;
    localStorage.removeItem(conversationStorageKey);
  }
  const storedVisitorMessageCount = Number(
    localStorage.getItem(visitorMessageCountStorageKey),
  );
  visitorMessageCount = conversationId && conversationToken &&
      Number.isInteger(storedVisitorMessageCount) && storedVisitorMessageCount >= 0
    ? Math.min(storedVisitorMessageCount, 3)
    : 0;
  if (!conversationId || !conversationToken) {
    localStorage.removeItem(visitorMessageCountStorageKey);
  }
  const storedRating = localStorage.getItem(conversationRatingStorageKey);
  conversationRated =
    conversationId && conversationToken &&
    (storedRating === "up" || storedRating === "down")
      ? storedRating
      : "";
  // A rated conversation was already thanked - never offer the rating again.
  ratingDismissed = conversationRated !== "";
  if (!conversationId || !conversationToken) {
    localStorage.removeItem(conversationRatingStorageKey);
  }
  renderRatingSelection();
  liveEnabled = session.live_human_escalation_enabled === true;
  hydrateLiveHistory = conversationId !== null;
  verificationEl.hidden = true;
  messagesEl.hidden = false;
  formEl.hidden = false;
  if (!chatInitialized) {
    chatInitialized = true;
    addBubble("assistant", params.greeting);
  }
  setLiveMode("ai");
  if (liveEnabled && conversationId && conversationToken) {
    void connectLive().catch(() => undefined);
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
  liveActionsEl.hidden = true;
  callbackEl.hidden = true;

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
    // The token is consumed as soon as the session is minted, but the widget
    // stays mounted (hidden) and would otherwise re-challenge every 5 minutes
    // when its spent token expires. wx-verify resets it when a fresh token is
    // actually needed.
    "refresh-expired": "never",
    callback: (token) => {
      verificationMessageEl.textContent = "Finishing verification…";
      postToParent({ type: "wx-turnstile", token });
    },
    "error-callback": () => showVerificationError(),
    "expired-callback": () => {
      // Only meaningful while we are still waiting to exchange the token -
      // after that the chat is running on its own session, so stay quiet.
      if (verificationEl.hidden) return;
      showVerificationError("Verification expired. Please try again.");
    },
    "timeout-callback": () =>
      showVerificationError("Verification timed out. Please try again."),
  });
}

export function handleParentMessage(event: MessageEvent) {
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
}

window.addEventListener("message", handleParentMessage);

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

function persistConversation(id: number, token?: string) {
  conversationId = id;
  if (conversationStorageKey) localStorage.setItem(conversationStorageKey, String(id));
  if (token) {
    conversationToken = token;
    if (conversationTokenStorageKey) localStorage.setItem(conversationTokenStorageKey, token);
  }
}

function clearConversationSession() {
  conversationId = null;
  conversationToken = "";
  visitorMessageCount = 0;
  conversationRated = "";
  ratingDismissed = false;
  localStorage.removeItem(conversationStorageKey);
  localStorage.removeItem(conversationTokenStorageKey);
  localStorage.removeItem(visitorMessageCountStorageKey);
  localStorage.removeItem(conversationRatingStorageKey);
  renderRatingSelection();
}

function showConnectionStatus(message: string, loading = false) {
  if (!connectionStatusBubble?.isConnected) {
    connectionStatusBubble = addBubble("assistant", "");
    connectionStatusBubble.classList.add("wx-live-status");
  } else if (loading) {
    // A repeat request reuses the resolved status bubble from the previous
    // attempt; bring it below any messages exchanged since.
    const row = connectionStatusBubble.closest(".wx-row");
    if (row) messagesEl.appendChild(row);
  }
  connectionStatusBubble.replaceChildren(document.createTextNode(message));
  if (loading) {
    const dots = document.createElement("span");
    dots.className = "wx-live-status-dots";
    dots.innerHTML = TYPING;
    connectionStatusBubble.append(" ", dots);
  }
  scrollToBottom();
}

function notifyTyping(active: boolean) {
  if (liveMode !== "human" || liveSocket?.readyState !== WebSocket.OPEN) return;
  const now = Date.now();
  if (active && typingSent && now - typingSentAt < TYPING_REFRESH_MS) return;
  if (!active && !typingSent) return;
  typingSent = active;
  typingSentAt = now;
  try {
    liveSocket.send(JSON.stringify({ version: 1, type: "typing", typing: active }));
  } catch {
    // Best-effort: a typing hint must never surface an error.
  }
}

function showOperatorTyping(active: boolean) {
  window.clearTimeout(operatorTypingTimer);
  if (!active) {
    operatorTypingRow?.remove();
    operatorTypingRow = null;
    return;
  }
  if (!operatorTypingRow?.isConnected) {
    const bubble = addBubble("assistant", "");
    bubble.classList.add("pending");
    bubble.innerHTML = TYPING;
    operatorTypingRow = bubble.closest<HTMLElement>(".wx-row") ?? bubble;
  } else {
    // Keep the dots below any message that arrived while they were up.
    messagesEl.appendChild(operatorTypingRow);
  }
  scrollToBottom();
  operatorTypingTimer = window.setTimeout(() => showOperatorTyping(false), TYPING_EXPIRE_MS);
}

async function liveResponseError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null) as { detail?: unknown } | null;
  return typeof body?.detail === "string"
    ? body.detail
    : `Live support failed (${response.status})`;
}

function setLiveMode(mode: LiveMode) {
  if (mode !== "human") {
    typingSent = false;
    showOperatorTyping(false);
  }
  liveMode = mode;
  const actionsWereHidden = liveActionsEl.hidden;
  const callbackWasHidden = callbackEl.hidden;
  const showTalk = liveEnabled && (
    mode === "waiting" || (
      mode === "ai" &&
      visitorMessageCount >= 3 &&
      !streaming &&
      conversationId !== null &&
      conversationToken.length > 0
    )
  );
  const showNewChat = mode === "closed";
  // Offer a rating on a real conversation once it has ended (closed) or once
  // the visitor has exchanged a few messages with the AI - independent of the
  // live-escalation feature, so AI-only sites can be rated too. Once rated
  // (and briefly thanked), the offer is gone for good.
  const showRating = !ratingDismissed &&
    conversationId !== null && conversationToken.length > 0 && (
      mode === "closed" || (mode === "ai" && visitorMessageCount >= 3 && !streaming)
    );
  liveActionsEl.hidden = !showTalk && !showNewChat && !showRating;
  livePromptEl.hidden = !showTalk;
  talkEl.hidden = !showTalk;
  talkEl.disabled = connectingToHuman;
  talkLabelEl.textContent = mode === "waiting" ? "Cancel request" : "Talk to a person";
  ratingEl.hidden = !showRating;
  newChatEl.hidden = !showNewChat;
  callbackEl.hidden = mode !== "pending_ticket";
  formEl.hidden = ["pending_ticket", "closed"].includes(mode);
  inputEl.disabled = mode === "waiting" || streaming || connectingToHuman;
  sendEl.disabled = mode === "waiting" || streaming || connectingToHuman;
  subtitleEl.textContent =
    mode === "human" ? "Live with the team" :
    mode === "waiting" ? "Finding someone…" :
    mode === "pending_ticket" ? "Currently unavailable" :
    mode === "closed" ? "Conversation closed" : "Online";
  // Un-hiding a panel between the messages and the composer shrinks the
  // message scrollport, clipping the newest bubble - re-pin to the bottom.
  if (
    (actionsWereHidden && !liveActionsEl.hidden) ||
    (callbackWasHidden && !callbackEl.hidden)
  ) {
    scrollToBottom();
  }
}

function recordVisitorMessage() {
  visitorMessageCount = Math.min(visitorMessageCount + 1, 3);
  if (visitorMessageCountStorageKey) {
    localStorage.setItem(visitorMessageCountStorageKey, String(visitorMessageCount));
  }
  setLiveMode(liveMode);
}

// How long "Thanks for your feedback." stays up before the rating bar hides.
const RATING_THANKS_MS = 1500;

function renderRatingSelection() {
  const rated = conversationRated !== "";
  rateUpEl.classList.toggle("selected", conversationRated === "up");
  rateDownEl.classList.toggle("selected", conversationRated === "down");
  rateUpEl.disabled = rated;
  rateDownEl.disabled = rated;
  ratingPromptEl.textContent = rated
    ? "Thanks for your feedback."
    : "How was this conversation?";
}

async function submitRating(value: Rating) {
  if (conversationRated || !conversationId || !conversationToken || !widgetToken) return;
  conversationRated = value; // optimistic; reverted below if the request fails
  renderRatingSelection();

  const request = () =>
    fetch(`${params.api}/widget/rating`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        widget_token: widgetToken,
        conversation_id: conversationId,
        conversation_token: conversationToken,
        rating: value,
      }),
    });

  try {
    let res = await request();
    if (res.status === 401) {
      const refreshed = await refreshToken();
      if (refreshed) {
        widgetToken = refreshed;
        res = await request();
      }
    }
    if (!res.ok) throw new Error(`Rating failed (${res.status})`);
    if (conversationRatingStorageKey) {
      localStorage.setItem(conversationRatingStorageKey, value);
    }
    // Leave the thanks up briefly, then retire the rating bar for good.
    const ratedConversation = conversationId;
    window.setTimeout(() => {
      if (conversationId !== ratedConversation) return; // a new chat started
      ratingDismissed = true;
      setLiveMode(liveMode);
    }, RATING_THANKS_MS);
  } catch {
    conversationRated = ""; // let the visitor try again
    renderRatingSelection();
    ratingPromptEl.textContent = "Couldn’t save your rating. Try again.";
  }
}

async function liveTicketRequest(): Promise<Response> {
  return fetch(`${params.api}/live/visitor/socket-ticket`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      widget_token: widgetToken,
      conversation_id: conversationId,
      conversation_token: conversationToken,
    }),
  });
}

async function openLiveConnection(): Promise<WebSocket> {
  if (liveMode === "closed") {
    throw new Error("This conversation has ended. Start a new conversation to continue.");
  }
  if (!conversationId || !conversationToken) {
    throw new Error("An existing conversation is required for live support.");
  }
  if (liveSocket?.readyState === WebSocket.OPEN) return liveSocket;
  liveSocket?.close();
  let response = await liveTicketRequest();
  if (response.status === 401) {
    const refreshed = await refreshToken();
    if (refreshed) {
      widgetToken = refreshed;
      response = await liveTicketRequest();
      if (response.status === 401) {
        // A fresh widget token still gets 401, so the stored conversation
        // session is expired and cannot be re-minted. Drop it (mirrors the
        // /chat/stream recovery in send()) so the visitor gets a working
        // chat instead of hitting this dead end on every open.
        clearConversationSession();
        displayedLiveMessageIds.clear();
        hydrateLiveHistory = false;
        setLiveMode("ai");
        throw new Error(
          "Your previous conversation has expired. Send a message to start a new one.",
        );
      }
    }
  }
  if (!response.ok) throw new Error(await liveResponseError(response));
  const ticket = await response.json() as {
    ticket: string;
    websocket_path: string;
    conversation_id: number;
  };
  persistConversation(ticket.conversation_id);
  const url = new URL(ticket.websocket_path, params.api);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url, ["live-v1", `ticket.${ticket.ticket}`]);
  liveSocket = socket;
  let opened = false;
  socket.onmessage = (message) => {
    let event: Record<string, unknown>;
    try { event = JSON.parse(message.data); } catch { return; }
    if (event.type === "state" && typeof event.mode === "string") {
      const previous = liveMode;
      const nextMode = event.mode as LiveMode;
      setLiveMode(nextMode);
      if (Array.isArray(event.messages)) {
        for (const raw of event.messages) {
          const item = raw as {
            id?: number;
            sender_type?: string;
            content?: string;
          };
          if (!item.id || displayedLiveMessageIds.has(item.id)) continue;
          displayedLiveMessageIds.add(item.id);
          if (
            hydrateLiveHistory &&
            item.content &&
            ["visitor", "operator", "ai"].includes(item.sender_type || "")
          ) {
            addBubble(
              item.sender_type === "visitor" ? "user" : "assistant",
              item.content,
            );
          }
        }
        hydrateLiveHistory = true;
      }
      const completesHandoff = pendingHandoffResult !== null &&
        ["waiting", "human", "pending_ticket"].includes(nextMode);
      if (completesHandoff && pendingHandoffResult) {
        const pending = pendingHandoffResult;
        pendingHandoffResult = null;
        window.clearTimeout(pending.timer);
        pending.resolve(nextMode);
      }
      if (previous !== nextMode) {
        // The "connecting" status bubble keeps its loader for the whole
        // waiting phase (a static "looking for someone" note reads as
        // stalled) and resolves in place into the outcome: accepted,
        // callback offer, cancelled, or closed.
        const fromWaiting = previous === "waiting" || completesHandoff;
        if (nextMode === "waiting") {
          showConnectionStatus("Give us a moment while we connect you…", true);
        } else if (nextMode === "human") {
          const message = "You’re now connected to the team.";
          if (fromWaiting) showConnectionStatus(message);
          else addBubble("assistant", message);
        } else if (nextMode === "pending_ticket") {
          const message = "No one is available right now. You can request a callback below.";
          if (fromWaiting) showConnectionStatus(message);
          else addBubble("assistant", message);
        } else if (nextMode === "ai" && previous === "waiting") {
          showConnectionStatus("Request cancelled. You’re back with the AI assistant.");
        } else if (nextMode === "closed") {
          const message = "This conversation has been closed.";
          if (previous === "waiting") showConnectionStatus(message);
          else addBubble("assistant", message);
        }
      }
    } else if (event.type === "message" && typeof event.message === "object" && event.message) {
      const item = event.message as { id?: number; sender_type?: string; content?: string };
      if (item.id) displayedLiveMessageIds.add(item.id);
      if (item.sender_type === "operator" && item.content) {
        showOperatorTyping(false);
        addBubble("assistant", item.content);
      }
    } else if (event.type === "typing" && event.actor_type === "operator") {
      showOperatorTyping(event.typing === true);
    } else if (event.type === "error") {
      const error = new Error(String(event.message || "Live support error."));
      if (pendingHandoffResult) {
        const pending = pendingHandoffResult;
        pendingHandoffResult = null;
        window.clearTimeout(pending.timer);
        pending.reject(error);
      } else {
        addBubble("assistant", error.message);
      }
    }
  };
  socket.onclose = () => {
    if (liveSocket === socket) {
      liveSocket = null;
      liveConnectionPromise = null;
      typingSent = false;
      if (pendingHandoffResult) {
        const pending = pendingHandoffResult;
        pendingHandoffResult = null;
        window.clearTimeout(pending.timer);
        pending.reject(new Error("Live connection closed."));
      }
      if (opened && conversationId && liveMode !== "closed") {
        window.setTimeout(() => void connectLive().catch(() => undefined), 1500);
      }
    }
  };
  return new Promise((resolve, reject) => {
    socket.onopen = () => {
      opened = true;
      resolve(socket);
    };
    socket.onerror = () => reject(new Error("Could not open live support."));
  });
}

function connectLive(): Promise<WebSocket> {
  if (liveSocket?.readyState === WebSocket.OPEN) return Promise.resolve(liveSocket);
  if (liveConnectionPromise) return liveConnectionPromise;
  const connection = openLiveConnection();
  liveConnectionPromise = connection;
  void connection.catch(() => {
    if (liveConnectionPromise === connection) liveConnectionPromise = null;
  });
  return connection;
}

async function liveAction(type: string, payload: object = {}) {
  const socket = await connectLive();
  socket.send(JSON.stringify({ version: 1, type, ...payload }));
}

function setStreaming(value: boolean) {
  streaming = value;
  setLiveMode(liveMode);
}

function waitForHandoffState(socket: WebSocket): Promise<LiveMode> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      if (pendingHandoffResult?.timer === timer) pendingHandoffResult = null;
      reject(new Error("Live support did not respond in time."));
    }, 10000);
    pendingHandoffResult = { resolve, reject, timer };
    socket.send(JSON.stringify({ version: 1, type: "escalate" }));
  });
}

function requestHumanHandoff(): void {
  if (handoffPromise || liveMode !== "ai" || streaming) return;
  connectingToHuman = true;
  setLiveMode(liveMode);
  showConnectionStatus("Give us a moment while we connect you…", true);

  const request = (async () => {
    try {
      const socket = await connectLive();
      await waitForHandoffState(socket);
    } catch {
      showConnectionStatus("We couldn’t connect you. Please try again.");
    } finally {
      connectingToHuman = false;
      if (handoffPromise === request) handoffPromise = null;
      setLiveMode(liveMode);
    }
  })();
  handoffPromise = request;
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
  if (liveMode === "human") {
    addBubble("user", trimmed);
    inputEl.value = "";
    notifyTyping(false);
    try {
      await liveAction("message", { content: trimmed, client_message_id: crypto.randomUUID() });
    } catch (error) {
      addBubble("assistant", (error as Error).message);
    }
    return;
  }
  if (liveMode !== "ai") return;
  addBubble("user", trimmed);
  inputEl.value = "";
  setStreaming(true);
  recordVisitorMessage();

  const pending = addBubble("assistant", "");
  pending.classList.add("pending");
  pending.innerHTML = TYPING;
  let answer = "";

  try {
    const controller = new AbortController();
    activeStream = controller;
    const request = () =>
      fetch(`${params.api}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          conversation_id: conversationId,
          widget_token: widgetToken,
          conversation_token: conversationToken || null,
        }),
        signal: controller.signal,
      });
    let res = await request();
    if (res.status === 401) {
      const refreshed = await refreshToken();
      if (refreshed) {
        widgetToken = refreshed;
        res = await request();
        if (res.status === 401 && conversationId && conversationToken) {
          // A fresh widget token still gets 401, so the stored conversation
          // session is expired and cannot be re-minted. Recover by starting a
          // new conversation instead of failing every message from now on.
          liveSocket?.close(1000, "conversation reset");
          liveSocket = null;
          liveConnectionPromise = null;
          clearConversationSession();
          displayedLiveMessageIds.clear();
          hydrateLiveHistory = false;
          recordVisitorMessage();
          res = await request();
        }
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
            persistConversation(
              event.conversation_id as number,
              event.conversation_token as string | undefined,
            );
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
          case "mode_changed":
          case "interrupted":
            if (event.mode === "closed") {
              // Server-side close (e.g. abuse moderation). The canned closing
              // message arrived as "token" events; keep the bubble. Setting
              // `answer` also stops the post-loop "(no response)" overwrite
              // when the close carried no text (already-closed conversation).
              if (!answer) {
                answer = "This conversation has been closed.";
                pending.textContent = answer;
              }
              pending.classList.remove("pending");
              setLiveMode("closed");
              scrollToBottom();
              break;
            }
            pending.remove();
            void connectLive().catch(() => undefined);
            break;
        }
      }
    }
    if (!answer && !pending.classList.contains("wx-error")) {
      pending.classList.remove("pending");
      pending.textContent = "(no response)";
    }
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      pending.remove();
      return;
    }
    pending.classList.remove("pending");
    pending.classList.add("wx-error");
    pending.textContent = (error as Error).message || "Connection error.";
  } finally {
    activeStream = null;
    setStreaming(false);
    inputEl.focus();
  }
}

talkEl.addEventListener("click", async () => {
  if (handoffPromise) return;
  if (liveMode === "ai") {
    requestHumanHandoff();
    return;
  }
  try {
    if (liveMode === "waiting") await liveAction("cancel");
  } catch (error) {
    addBubble("assistant", (error as Error).message);
  }
});

rateUpEl.addEventListener("click", () => void submitRating("up"));
rateDownEl.addEventListener("click", () => void submitRating("down"));

newChatEl.addEventListener("click", () => {
  liveSocket?.close(1000, "new conversation");
  liveSocket = null;
  liveConnectionPromise = null;
  handoffPromise = null;
  connectingToHuman = false;
  connectionStatusBubble = null;
  clearConversationSession();
  displayedLiveMessageIds.clear();
  hydrateLiveHistory = false;
  messagesEl.replaceChildren();
  addBubble("assistant", params.greeting);
  setLiveMode("ai");
});

callbackEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await liveAction("ticket", {
      customer_name: callbackNameEl.value.trim(),
      customer_email: callbackEmailEl.value.trim(),
      customer_message: callbackMessageEl.value.trim(),
    });
  } catch (error) {
    addBubble("assistant", (error as Error).message);
  }
});

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  void send(inputEl.value);
});

inputEl.addEventListener("input", () => {
  notifyTyping(inputEl.value.trim().length > 0);
});

window.addEventListener("load", renderVerification, { once: true });
