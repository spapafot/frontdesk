interface Props {
  /** Diameter/border sizing classes. Defaults to a small inline spinner. */
  className?: string;
  label?: string;
}

/**
 * Minimal spinning ring for full-screen or inline "working" states where a
 * shape-matched skeleton doesn't fit (e.g. the initial auth session check).
 * Uses Tailwind's built-in `animate-spin`.
 */
export function Spinner({ className = "h-5 w-5", label = "Loading" }: Props) {
  return (
    <span
      role="status"
      aria-label={label}
      className={`inline-block animate-spin rounded-full border-2 border-slate-300 border-t-sky-600 motion-reduce:animate-none ${className}`}
    />
  );
}
