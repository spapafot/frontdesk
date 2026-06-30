import { useCallback, useEffect, useRef, useState } from "react";
import { WS_BASE } from "../api/client";
import { AudioFrameQueue } from "../lib/audioFrameQueue";

export type VoiceStatus =
  | "idle"
  | "connecting"
  | "recording"
  | "thinking"
  | "speaking"
  | "error";

interface Options {
  conversationId: number | null;
  onConversationId?: (id: number) => void;
  // Playback speed for the synthesized audio (from the user's tts_speed setting).
  getRate?: () => number;
}

function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  const candidates = ["audio/webm", "audio/mp4", "audio/ogg"];
  return candidates.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
}

export function useVoiceSocket({ conversationId, onConversationId, getRate }: Options) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [transcript, setTranscript] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const conversationRef = useRef<number | null>(conversationId);
  const onConversationIdRef = useRef(onConversationId);
  const getRateRef = useRef(getRate);
  const generationDoneRef = useRef(false);
  conversationRef.current = conversationId;
  onConversationIdRef.current = onConversationId;
  getRateRef.current = getRate;

  const queueRef = useRef<AudioFrameQueue | null>(null);
  const getQueue = useCallback(() => {
    if (!queueRef.current) {
      queueRef.current = new AudioFrameQueue(
        () => getRateRef.current?.() ?? 1,
        () => {
          // Drained: only truly idle once generation has also finished.
          if (generationDoneRef.current) setStatus("idle");
        }
      );
    }
    return queueRef.current;
  }, []);

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices &&
    typeof MediaRecorder !== "undefined" &&
    typeof WebSocket !== "undefined";

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return wsRef.current;
    setStatus("connecting");
    const ws = new WebSocket(`${WS_BASE}/voice/ws`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("idle");
      ws.send(
        JSON.stringify({ type: "config", conversation_id: conversationRef.current })
      );
    };
    ws.onmessage = (event) => {
      if (typeof event.data !== "string") {
        setStatus("speaking");
        getQueue().push(event.data as ArrayBuffer);
        return;
      }
      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      switch (msg.type) {
        case "conversation":
          conversationRef.current = msg.conversation_id as number;
          onConversationIdRef.current?.(msg.conversation_id as number);
          break;
        case "transcript":
          setTranscript((msg.text as string) || "");
          setAnswer("");
          break;
        case "token":
          setAnswer((prev) => prev + (msg.content as string));
          break;
        case "done":
          generationDoneRef.current = true;
          // If no audio is left to play, we're done now; otherwise the queue's
          // onIdle callback will flip us back to idle when playback finishes.
          if (!queueRef.current?.isActive()) setStatus("idle");
          break;
        case "error":
          setError((msg.message as string) || "Voice error.");
          setStatus("error");
          break;
      }
    };
    ws.onerror = () => {
      setError("Voice connection error.");
      setStatus("error");
    };
    ws.onclose = () => {
      if (wsRef.current === ws) wsRef.current = null;
    };
    return ws;
  }, [getQueue]);

  const startRecording = useCallback(async () => {
    if (!supported) {
      setError("Voice is not supported in this browser.");
      return;
    }
    setError(null);
    // Barge-in: stop playback from the previous turn, tell the server to stop
    // generating it, and reset state before opening/using the socket.
    queueRef.current?.stop();
    generationDoneRef.current = false;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "cancel" }));
    }
    const ws = connect();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorderRef.current = recorder;

      const sendConfig = () =>
        ws.readyState === WebSocket.OPEN &&
        ws.send(
          JSON.stringify({
            type: "config",
            conversation_id: conversationRef.current,
            mime: recorder.mimeType || mimeType || "audio/webm",
          })
        );
      if (ws.readyState === WebSocket.OPEN) sendConfig();
      else ws.addEventListener("open", sendConfig, { once: true });

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
          e.data.arrayBuffer().then((buf) => {
            if (ws.readyState === WebSocket.OPEN) ws.send(buf);
          });
        }
      };
      recorder.onstop = () => {
        // Give the final dataavailable a tick to flush, then close the utterance.
        setTimeout(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "audio_end" }));
        }, 50);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recorderRef.current = null;
      };
      recorder.start(250);
      setStatus("recording");
    } catch (err) {
      setError(
        (err as Error).name === "NotAllowedError"
          ? "Microphone permission denied."
          : `Could not start recording: ${(err as Error).message}`
      );
      setStatus("error");
    }
  }, [connect, supported]);

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      setStatus("thinking");
      // Warm the audio output device now, while we still have the user gesture,
      // so the first synthesized word is not clipped when it arrives.
      getQueue().start();
      recorder.stop();
    }
  }, [getQueue]);

  const cancel = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "cancel" }));
  }, []);

  useEffect(() => {
    return () => {
      recorderRef.current?.state !== "inactive" && recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((t) => t.stop());
      queueRef.current?.stop();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []);

  return {
    status,
    transcript,
    answer,
    error,
    supported,
    startRecording,
    stopRecording,
    cancel,
    setStatus,
  };
}
