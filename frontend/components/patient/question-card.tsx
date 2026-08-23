"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * One question per card, at most two cards per screen (§6, Phase 2). The card
 * holds no enter/exit animation — step transitions come from <StepTransition>
 * in step-progress.tsx, which is the single owner of wizard motion.
 *
 * Copy is passed in and never rephrased here; the component adds no clinical
 * interpretation of its own (§5.4).
 */

type QuestionCardProps = {
  /** The question itself, in Persian. Kept short and plain — audience is elderly. */
  question: string;
  /** Optional plain-language clarification shown under the question. */
  hint?: ReactNode;
  /** Marks the question as required; renders a text marker, never colour alone. */
  required?: boolean;
  /** Validation message. Rendered with role="alert" so it is announced. */
  error?: string;
  /** The answer controls — <ChoiceOption> rows, an input, an upload field. */
  children: ReactNode;
  className?: string;
};

export function QuestionCard({
  question,
  hint,
  required = false,
  error,
  children,
  className,
}: QuestionCardProps) {
  return (
    <section
      data-testid="question-card"
      aria-invalid={error ? true : undefined}
      className={cn(
        "rounded-medical border bg-white p-5 shadow-soft transition-colors duration-300",
        error ? "border-critical" : "border-primary/15",
        className,
      )}
    >
      <h2 className="text-xl font-semibold leading-relaxed">
        {question}
        {required ? (
          <span className="ms-2 align-middle text-sm font-normal text-slate-500">
            (الزامی)
          </span>
        ) : null}
      </h2>

      {hint ? <p className="mt-2 text-base leading-relaxed text-slate-600">{hint}</p> : null}

      <div className="mt-4 flex flex-col gap-3">{children}</div>

      {error ? (
        <p
          role="alert"
          data-testid="question-card-error"
          className="mt-4 rounded-2xl bg-critical-surface px-4 py-3 text-base font-medium text-critical"
        >
          {error}
        </p>
      ) : null}
    </section>
  );
}

type ChoiceOptionProps = {
  /** Shared across every option of one question — this is the radio group name. */
  name: string;
  value: string;
  checked: boolean;
  onSelect: (value: string) => void;
  /** Option label. Wrap any Latin/numeric fragment in <BidiText> at the call site. */
  children: ReactNode;
  disabled?: boolean;
  className?: string;
};

/**
 * A single answer choice. `min-h-14` rather than a fixed `h-14` so the row still
 * clears the touch-target floor when a long Persian label wraps to two lines.
 *
 * A native radio drives it, so arrow-key navigation, roving tab index and the
 * radiogroup semantics come from the platform rather than being re-implemented.
 * The input is `sr-only` but never `hidden` — it stays focusable, and the ring
 * is drawn on the label via `has-[:focus-visible]`.
 */
export function ChoiceOption({
  name,
  value,
  checked,
  onSelect,
  children,
  disabled = false,
  className,
}: ChoiceOptionProps) {
  return (
    <label
      data-testid="choice-option"
      data-checked={checked ? "true" : "false"}
      className={cn(
        "flex min-h-14 cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3",
        "text-base leading-relaxed transition-colors duration-200",
        "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-offset-2",
        checked ? "border-primary bg-primary-surface font-medium" : "border-slate-200 bg-white",
        disabled ? "cursor-not-allowed opacity-60" : "hover:border-primary/50",
        className,
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onSelect(value)}
        className="sr-only"
      />
      {/* Decorative: the checked state is already conveyed by the native radio. */}
      <span
        aria-hidden="true"
        className={cn(
          "grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 transition-colors duration-200",
          checked ? "border-primary" : "border-slate-300",
        )}
      >
        <span
          className={cn(
            "h-3 w-3 rounded-full bg-primary transition-transform duration-200",
            checked ? "scale-100" : "scale-0",
          )}
        />
      </span>
      <span>{children}</span>
    </label>
  );
}
