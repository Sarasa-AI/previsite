import { cx } from "./cx";
import { ClinicalValueState } from "@/components/ui";

export type StatusChipProps = {
  status: string;
  className?: string;
};

export function StatusChip({ status, className }: StatusChipProps) {
  return (
    <ClinicalValueState
      state="not-verified"
      label={status}
      className={cx(className)}
      aria-label={`Status ${status}`}
      title="مقدار وضعیت از قرارداد نمایش داده شده و در frontend تفسیر نشده است"
    />
  );
}
