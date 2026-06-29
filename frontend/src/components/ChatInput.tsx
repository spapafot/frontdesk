import { FormEvent, useState } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
  };

  return (
    <form onSubmit={submit} className="flex gap-2 border-t border-slate-200 bg-white p-3">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Ask a question..."
        className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="rounded-full bg-sky-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}
