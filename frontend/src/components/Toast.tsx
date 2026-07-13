import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";

type ToastVariant = "error" | "success";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void;
}

const DISMISS_MS = 4000;

// No-op default so components can call useToast() without a provider (e.g. in
// isolated component tests), mirroring AuthContext/SiteContext defaults.
const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

/** Fire a transient, auto-dismissing toast from anywhere in the tree. */
export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, variant: ToastVariant = "error") => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, message, variant }]);
      setTimeout(() => dismiss(id), DISMISS_MS);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2"
        role="status"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2 text-sm shadow-lg ${
              t.variant === "error"
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
            }`}
          >
            <span className="min-w-0 flex-1">{t.message}</span>
            <button
              type="button"
              aria-label="Dismiss"
              onClick={() => dismiss(t.id)}
              className="shrink-0 rounded p-0.5 text-current opacity-60 transition hover:opacity-100"
            >
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path
                  d="M5 5l10 10M15 5L5 15"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
