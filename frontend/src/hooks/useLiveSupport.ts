import { useCallback, useEffect, useRef, useState } from "react";
import {
  LiveMessage,
  LiveState,
  openLiveSocket,
  operatorSocketTicket,
} from "../api/live";

interface WireEvent extends Partial<LiveState> {
  version: 1;
  type: string;
  message?: LiveMessage | string;
  created?: boolean;
  online?: boolean;
  actor_type?: string;
  typing?: boolean;
}

// While composing, refresh the outbound typing signal at most every
// TYPING_REFRESH_MS; the inbound indicator hides after TYPING_EXPIRE_MS
// without a refresh so a lost "stopped typing" event can never strand it.
const TYPING_REFRESH_MS = 2000;
const TYPING_EXPIRE_MS = 5000;

function mergeMessages(
  current: LiveMessage[] = [],
  incoming: LiveMessage[] = [],
): LiveMessage[] {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return [...byId.values()].sort((left, right) => left.id - right.id);
}

function send(socket: WebSocket | null, type: string, payload: object = {}): void {
  if (socket?.readyState !== WebSocket.OPEN) throw new Error("Live connection is not ready.");
  socket.send(JSON.stringify({ version: 1, type, ...payload }));
}

export function useLiveInbox(
  siteId: number | null,
  enabled: boolean,
  onWaiting: (conversationId: number) => void,
  onTransition?: (state: Partial<LiveState> & { conversation_id: number }) => void,
) {
  const socketRef = useRef<WebSocket | null>(null);
  const onlineRef = useRef(false);
  const audioRef = useRef<AudioContext | null>(null);
  const onTransitionRef = useRef(onTransition);
  const [online, setOnlineState] = useState(false);
  const [connected, setConnected] = useState(false);
  const [waiting, setWaiting] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onTransitionRef.current = onTransition;
  }, [onTransition]);

  useEffect(() => {
    if (!enabled || siteId === null) return;
    let stopped = false;
    let reconnect: number | undefined;
    const connect = async () => {
      try {
        const ticket = await operatorSocketTicket(siteId, "inbox");
        if (stopped) return;
        const socket = openLiveSocket(ticket);
        socketRef.current = socket;
        socket.onopen = () => {
          setConnected(true);
          setError(null);
          send(socket, "presence", { online: onlineRef.current });
        };
        socket.onmessage = (event) => {
          const message = JSON.parse(event.data) as WireEvent;
          if (message.type === "waiting" && message.conversation_id) {
            const id = message.conversation_id;
            setWaiting((current) => (current.includes(id) ? current : [...current, id]));
            onWaiting(id);
            const context = audioRef.current;
            if (context) {
              const oscillator = context.createOscillator();
              const gain = context.createGain();
              gain.gain.value = 0.05;
              oscillator.frequency.value = 720;
              oscillator.connect(gain).connect(context.destination);
              oscillator.start();
              oscillator.stop(context.currentTime + 0.12);
            }
          } else if (message.type === "transition" && message.conversation_id) {
            onTransitionRef.current?.(message as Partial<LiveState> & {
              conversation_id: number;
            });
          }
        };
        socket.onclose = () => {
          setConnected(false);
          if (!stopped) reconnect = window.setTimeout(connect, 2000);
        };
      } catch (reason) {
        setError((reason as Error).message);
        if (!stopped) reconnect = window.setTimeout(connect, 3000);
      }
    };
    void connect();
    return () => {
      stopped = true;
      if (reconnect) clearTimeout(reconnect);
      socketRef.current?.close(1000, "site changed");
      socketRef.current = null;
      setConnected(false);
    };
  }, [enabled, onWaiting, siteId]);

  const setOnline = useCallback((value: boolean) => {
    onlineRef.current = value;
    setOnlineState(value);
    if (value && !audioRef.current) audioRef.current = new AudioContext();
    try {
      send(socketRef.current, "presence", { online: value });
    } catch (reason) {
      setError((reason as Error).message);
    }
  }, []);

  const clearWaiting = useCallback((conversationId: number) => {
    setWaiting((current) => current.filter((id) => id !== conversationId));
  }, []);

  return { online, connected, waiting, error, setOnline, clearWaiting };
}

export function useLiveConversation(
  siteId: number | null,
  conversationId: number | null,
  enabled: boolean,
  onStateChange?: (state: LiveState) => void,
) {
  const socketRef = useRef<WebSocket | null>(null);
  const modeRef = useRef<LiveState["mode"] | null>(null);
  const stateRef = useRef<LiveState | null>(null);
  const onStateChangeRef = useRef(onStateChange);
  const typingSentRef = useRef(false);
  const typingSentAtRef = useRef(0);
  const typingExpiryRef = useRef<number | undefined>(undefined);
  const [state, setState] = useState<LiveState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visitorTyping, setVisitorTyping] = useState(false);

  useEffect(() => {
    onStateChangeRef.current = onStateChange;
  }, [onStateChange]);

  useEffect(() => {
    setState(null);
    setVisitorTyping(false);
    stateRef.current = null;
    modeRef.current = null;
    typingSentRef.current = false;
    window.clearTimeout(typingExpiryRef.current);
    if (!enabled || siteId === null || conversationId === null) return;
    let stopped = false;
    let reconnect: number | undefined;
    const connect = async () => {
      try {
        const ticket = await operatorSocketTicket(siteId, "conversation", conversationId);
        if (stopped) return;
        const socket = openLiveSocket(ticket);
        socketRef.current = socket;
        socket.onopen = () => setError(null);
        socket.onmessage = (event) => {
          const message = JSON.parse(event.data) as WireEvent;
          if (message.type === "state") {
            if (message.mode) modeRef.current = message.mode;
            const current = stateRef.current;
            const next = ({
              ...(current ?? {}),
              ...message,
              messages: message.messages
                ? mergeMessages(current?.messages, message.messages)
                : current?.messages ?? [],
            }) as LiveState;
            stateRef.current = next;
            setState(next);
            onStateChangeRef.current?.(next);
          } else if (message.type === "message" && typeof message.message === "object") {
            const incoming = message.message as LiveMessage;
            if (incoming.sender_type === "visitor") {
              window.clearTimeout(typingExpiryRef.current);
              setVisitorTyping(false);
            }
            const current = stateRef.current;
            if (current) {
              const next = {
                ...current,
                messages: mergeMessages(current.messages, [incoming]),
              };
              stateRef.current = next;
              setState(next);
            }
          } else if (message.type === "typing" && message.actor_type === "visitor") {
            window.clearTimeout(typingExpiryRef.current);
            setVisitorTyping(message.typing === true);
            if (message.typing === true) {
              typingExpiryRef.current = window.setTimeout(
                () => setVisitorTyping(false),
                TYPING_EXPIRE_MS,
              );
            }
          } else if (message.type === "error") {
            setError(typeof message.message === "string" ? message.message : "Live action failed.");
          }
        };
        socket.onclose = () => {
          if (socketRef.current === socket) socketRef.current = null;
          typingSentRef.current = false;
          if (!stopped && modeRef.current !== "closed") {
            reconnect = window.setTimeout(connect, 1500);
          }
        };
      } catch (reason) {
        setError((reason as Error).message);
        if (!stopped && modeRef.current !== "closed") {
          reconnect = window.setTimeout(connect, 3000);
        }
      }
    };
    void connect();
    return () => {
      stopped = true;
      if (reconnect) clearTimeout(reconnect);
      socketRef.current?.close(1000, "conversation changed");
      socketRef.current = null;
    };
  }, [conversationId, enabled, siteId]);

  const action = useCallback((type: string, payload: object = {}) => {
    try {
      send(socketRef.current, type, payload);
      setError(null);
    } catch (reason) {
      setError((reason as Error).message);
    }
  }, []);

  const notifyTyping = useCallback((active: boolean) => {
    const now = Date.now();
    if (active && typingSentRef.current && now - typingSentAtRef.current < TYPING_REFRESH_MS) {
      return;
    }
    if (!active && !typingSentRef.current) return;
    try {
      send(socketRef.current, "typing", { typing: active });
      typingSentRef.current = active;
      typingSentAtRef.current = now;
    } catch {
      // Best-effort: a typing hint must never surface an error.
    }
  }, []);

  return { state, error, action, visitorTyping, notifyTyping };
}
