import useSWR from "swr";
import { getSettings, settingsKey } from "../api/settings";
import { useVoiceSocket } from "../hooks/useVoiceSocket";

interface Props {
  selectedConversationId: number | null;
  onConversationCreated: (id: number) => void;
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-8 w-8" fill="currentColor" aria-hidden="true">
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z" />
    </svg>
  );
}

const STATUS_LABEL: Record<string, string> = {
  idle: "Tap to speak",
  connecting: "Connecting...",
  recording: "Listening... tap to send",
  thinking: "Thinking...",
  speaking: "Speaking...",
  error: "Something went wrong",
};

export function VoicePage({ selectedConversationId, onConversationCreated }: Props) {
  const { data: settings } = useSWR(settingsKey, getSettings);
  const { status, transcript, answer, error, supported, startRecording, stopRecording } =
    useVoiceSocket({
      conversationId: selectedConversationId,
      onConversationId: onConversationCreated,
      getRate: () => settings?.tts_speed ?? 1.1,
    });

  const isRecording = status === "recording";
  const busy = status === "thinking" || status === "speaking";

  const onToggle = () => {
    if (isRecording) stopRecording();
    else if (!busy) startRecording();
  };

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-2xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-sm font-semibold text-slate-800">Voice</h1>
            <p className="text-xs text-slate-500">Talk to your assistant hands-free</p>
          </div>
        </div>
      </header>

      <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4">
        {!supported && (
          <p className="text-sm text-red-600">
            Voice is not supported in this browser.
          </p>
        )}

        <button
          type="button"
          onClick={onToggle}
          disabled={!supported || busy}
          className={`flex h-28 w-28 items-center justify-center rounded-full text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60 ${
            isRecording
              ? "animate-pulse bg-red-600"
              : busy
                ? "bg-slate-400"
                : "bg-sky-600 hover:bg-sky-700"
          }`}
          title={STATUS_LABEL[status]}
        >
          <MicIcon />
        </button>

        <p className="text-sm font-medium text-slate-600">
          {error ?? STATUS_LABEL[status]}
        </p>

        <div className="w-full max-w-xl space-y-4">
          {transcript && (
            <div className="rounded-2xl bg-slate-100 px-4 py-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                You said
              </p>
              <p className="text-sm text-slate-800">{transcript}</p>
            </div>
          )}
          {answer && (
            <div className="rounded-2xl bg-sky-50 px-4 py-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-500">
                Assistant
              </p>
              <p className="text-sm text-slate-800">{answer}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
