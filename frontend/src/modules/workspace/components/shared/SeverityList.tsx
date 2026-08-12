import type { ReactNode } from "react";
import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import type { SeverityLevel } from "../types";
import { ExpandableBlock } from "./ExpandableBlock";
import { cx } from "./cx";

export type SeverityListItem = {
  readonly id: string;
  readonly title: string;
  readonly severity: SeverityLevel;
  readonly explanation: ReactNode;
};

export type SeverityListProps = {
  items: readonly SeverityListItem[];
  className?: string;
  "aria-label"?: string;
};

const SEVERITY_STYLES: Record<SeverityLevel, string> = {
  critical: "text-danger",
  warning: "text-trust",
  info: "text-ink/70",
};

function SeverityIcon({ severity }: { severity: SeverityLevel }) {
  if (severity === "critical") {
    return <AlertCircle className="size-4 shrink-0 text-danger" aria-hidden="true" />;
  }
  if (severity === "warning") {
    return <AlertTriangle className="size-4 shrink-0 text-trust" aria-hidden="true" />;
  }
  return <Info className="size-4 shrink-0 text-ink/60" aria-hidden="true" />;
}

/** Product-agnostic severity-colored expandable items (alerts, red flags, etc.). */
export function SeverityList({
  items,
  className,
  "aria-label": ariaLabel = "Severity list",
}: SeverityListProps) {
  return (
    <div className={cx("rounded-md border border-trust/10", className)} aria-label={ariaLabel}>
      {items.map((item) => (
        <ExpandableBlock
          key={item.id}
          className="px-2"
          summary={
            <span className="flex items-center gap-2">
              <SeverityIcon severity={item.severity} />
              <span className={cx("font-medium", SEVERITY_STYLES[item.severity])}>
                {item.title}
              </span>
              <span className="sr-only">{item.severity}</span>
            </span>
          }
        >
          {item.explanation}
        </ExpandableBlock>
      ))}
    </div>
  );
}
