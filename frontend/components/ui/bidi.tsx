import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type BidiTextProps = HTMLAttributes<HTMLSpanElement> & { children: ReactNode };

export function BidiText({ className, children, ...props }: BidiTextProps) {
  return <span dir="auto" className={cn("tai-bidi-value", className)} {...props}>{children}</span>;
}

export function LtrValue({ className, children, ...props }: BidiTextProps) {
  return <bdi dir="ltr" className={cn("tai-ltr-value", className)} {...props}>{children}</bdi>;
}

export function NumericValue({ className, children, ...props }: BidiTextProps) {
  return <bdi dir="ltr" className={cn("tai-ltr-value tai-numeric-value", className)} {...props}>{children}</bdi>;
}

export const MrnValue = LtrValue;
export const DateValue = NumericValue;
export const DoseValue = NumericValue;
export const UnitValue = LtrValue;
