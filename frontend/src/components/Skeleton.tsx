interface Props {
  /** Extra Tailwind classes to size/shape the block (e.g. "h-4 w-2/3"). */
  className?: string;
}

/**
 * Base skeleton block - a pulsing grey rectangle used to mirror the shape of
 * content while it loads. This is the first shared UI primitive in the app;
 * view-specific skeletons are composed from it inline in each view. Matches the
 * existing `animate-pulse` idiom (MessageBubble typing dots) and the grey-bar
 * placeholder look in WidgetPreview.
 */
export function Skeleton({ className = "" }: Props) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded bg-slate-200 motion-reduce:animate-none ${className}`}
    />
  );
}
