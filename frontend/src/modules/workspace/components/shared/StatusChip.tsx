import { cx } from "./cx";

export type StatusChipProps = {
  status: string;
  className?: string;
};

export function StatusChip({ status, className }: StatusChipProps) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded border border-mint/50 bg-mint/30 px-1.5 py-0.5 text-xs font-medium text-trust",
        className,
      )}
      aria-label={`Status ${status}`}
    >
      {status}
    </span>
  );
}
