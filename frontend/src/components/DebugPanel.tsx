interface Props {
  enabled: boolean;
  onToggle: (value: boolean) => void;
}

export function DebugPanel({ enabled, onToggle }: Props) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-500">
      <span>Debug</span>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={() => onToggle(!enabled)}
        className={`relative h-5 w-9 rounded-full transition ${
          enabled ? "bg-sky-600" : "bg-slate-300"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition ${
            enabled ? "left-4" : "left-0.5"
          }`}
        />
      </button>
    </label>
  );
}
