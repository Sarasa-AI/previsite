import { cx } from "./cx";

export type PriorityBadgeProps = {
  priority: string;
  className?: string;
};

const PRIORITY_STYLES: Record<string, string> = {
  p0: "border-danger/40 bg-danger/10 text-danger",
  p1: "border-trust/30 bg-trust/10 text-trust",
  p2: "border-ink/20 bg-clinical text-ink",
  p3: "border-ink/15 bg-white text-ink/70",
};

export function PriorityBadge({ priority, className }: PriorityBadgeProps) {
  const style = PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.p2;

  return (
    <span
      className={cx(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide",
        style,
        className,
      )}
      aria-label={`Priority ${priority}`}
    >
      {priority}
    </span>
  );
}
