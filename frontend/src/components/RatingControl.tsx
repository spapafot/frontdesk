import { useEffect, useState } from "react";
import { Rating } from "../api/conversations";

interface Props {
  rating: Rating | null;
  disabled?: boolean;
  onSubmit: (rating: Rating) => void | Promise<void>;
}

function ThumbIcon({ down }: { down?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`h-4 w-4 ${down ? "rotate-180" : ""}`}
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M2 21h2c.55 0 1-.45 1-1v-9c0-.55-.45-1-1-1H2v11zm19.83-7.12c.11-.25.17-.52.17-.8V11c0-1.1-.9-2-2-2h-5.5l.92-4.65c.05-.22.02-.46-.08-.66a4.8 4.8 0 0 0-.88-1.17L14 2 7.59 8.41C7.21 8.79 7 9.3 7 9.83v7.84A2.34 2.34 0 0 0 9.34 20h8.11c.7 0 1.36-.37 1.72-.97l2.66-5.15z" />
    </svg>
  );
}

export function RatingControl({ rating, disabled, onSubmit }: Props) {
  const [selected, setSelected] = useState<Rating | null>(rating);

  useEffect(() => {
    setSelected(rating);
  }, [rating]);

  const choose = async (value: Rating) => {
    setSelected(value);
    await onSubmit(value);
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400">Helpful?</span>
      <button
        type="button"
        disabled={disabled}
        title="Helpful"
        onClick={() => choose("up")}
        className={`rounded p-1 transition disabled:opacity-40 ${
          selected === "up"
            ? "bg-emerald-100 text-emerald-700"
            : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        }`}
      >
        <ThumbIcon />
      </button>
      <button
        type="button"
        disabled={disabled}
        title="Not helpful"
        onClick={() => choose("down")}
        className={`rounded p-1 transition disabled:opacity-40 ${
          selected === "down"
            ? "bg-red-100 text-red-600"
            : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        }`}
      >
        <ThumbIcon down />
      </button>
    </div>
  );
}
