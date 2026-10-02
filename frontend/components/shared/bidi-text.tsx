import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type BidiTextProps = {
  /**
   * A single Latin-script or numeric fragment — a dose, a lab unit, a date,
   * an identifier. Never a whole mixed-language sentence: wrapping a sentence
   * would force its Persian words into LTR order and scramble the reading.
   */
  children: ReactNode;
  /** Renders as <span> by default; pass "bdi" where nesting depth is a concern. */
  as?: "span" | "bdi";
  className?: string;
};

/**
 * Isolates an LTR fragment inside RTL copy.
 *
 * `dir="ltr"` carries `unicode-bidi: isolate` from the UA stylesheet, so the
 * fragment resolves its own direction without leaking bidi context into the
 * surrounding Persian text — the failure it prevents is "۵ mg" rendering as
 * "mg ۵", or a date's segments reordering.
 *
 * Holds no theme opinion (§2): colour and size arrive via `className` from the
 * calling route.
 */
export function BidiText({ children, as = "span", className }: BidiTextProps) {
  const Tag = as;
  return (
    <Tag dir="ltr" lang="en" className={cn("inline-block", className)}>
      {children}
    </Tag>
  );
}
