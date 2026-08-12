import { cx } from "./cx";

export type SourceIndicatorProps = {
  source: string;
  className?: string;
};

export function SourceIndicator({ source, className }: SourceIndicatorProps) {
  return (
    <span
      className={cx("inline-flex items-center text-xs text-ink/60", className)}
      aria-label={`Source ${source}`}
    >
      {source}
    </span>
  );
}
