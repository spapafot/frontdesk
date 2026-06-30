import { FormEvent, useState } from "react";
import { transcribeAudio } from "../api/speech";
import { useVoiceRecorder } from "../hooks/useVoiceRecorder";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z" />
    </svg>
  );
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const [transcribing, setTranscribing] = useState(false);
  const { isRecording, error, supported, start, stop } = useVoiceRecorder();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
  };

  const toggleMic = async () => {
    if (disabled || transcribing) return;
    if (isRecording) {
      const blob = await stop();
      if (!blob) return;
      setTranscribing(true);
      try {
        const text = await transcribeAudio(blob);
        if (text.trim()) onSend(text.trim());
      } catch {
        // Surfaced via the recorder error/placeholder; keep input usable.
      } finally {
        setTranscribing(false);
      }
    } else {
      await start();
    }
  };

  const micState = isRecording ? "recording" : transcribing ? "transcribing" : "idle";

  return (
    <div className="border-t border-slate-200 bg-white">
      <div className="mx-auto w-full max-w-2xl">
        {(error || isRecording || transcribing) && (
          <div className="px-4 pt-2 text-xs text-slate-500">
            {error
              ? <span className="text-red-600">{error}</span>
              : isRecording
                ? "Listening... click the mic again to send."
                : "Transcribing..."}
          </div>
        )}
        <form onSubmit={submit} className="flex gap-2 px-4 py-3">
        {supported && (
          <button
            type="button"
            onClick={toggleMic}
            disabled={disabled || transcribing}
            title={isRecording ? "Stop and send" : "Record a voice message"}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition disabled:cursor-not-allowed disabled:opacity-50 ${
              micState === "recording"
                ? "animate-pulse bg-red-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            <MicIcon />
          </button>
        )}
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={isRecording ? "Listening..." : "Ask a question..."}
          disabled={transcribing}
          className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-full bg-sky-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </form>
      </div>
    </div>
  );
}
