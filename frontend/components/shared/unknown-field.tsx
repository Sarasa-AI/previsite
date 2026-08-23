import { cn } from "@/lib/utils";

/**
 * The literal text rendered when a clinical field has no usable value.
 *
 * Exported so callers and tests assert against one source of truth instead of
 * re-typing Persian literals — a re-typed literal is exactly where a stray
 * zero-width character or a spelling drift enters unnoticed.
 */
export const UNKNOWN_FIELD_TEXT = {
  /**
   * Value absent or not determinable: OCR landed below the confidence gate,
   * the patient answered "I don't know", the source was illegible.
   */
  unknown: "نامشخص",
  /** Nothing was ever entered into this field. */
  "not-recorded": "ثبت نشده",
} as const;

export type UnknownFieldVariant = keyof typeof UNKNOWN_FIELD_TEXT;

type UnknownFieldProps = {
  /**
   * Defaults to `"unknown"` — the fail-closed choice (§5.1). "ثبت نشده" asserts
   * a fact about the record (that it is empty); "نامشخص" only says the value
   * isn't determined. When the caller can't distinguish the two, the weaker
   * claim is the correct one, so it is the default rather than an explicit
   * opt-in that a caller can forget to make.
   */
  variant?: UnknownFieldVariant;
  className?: string;
};

/**
 * The only sanctioned way to render a missing clinical value (§5.2). Always
 * returns visible text — there is no prop, and no combination of props, that
 * makes this render an empty element. That mirrors the OCR pipeline's
 * confidence-gated fallback: a blank cell is indistinguishable from "we never
 * asked", which is the ambiguity the rule exists to remove.
 *
 * Holds no theme opinion (§2): it lives in `shared/`, so it carries neither a
 * patient nor a clinician token and inherits colour from its cell. Two
 * deliberate omissions in the default styling:
 *
 * - **No muted colour or `opacity-*`.** The obvious treatment — dim it so it
 *   reads as "not a real value" — cuts the contrast of a safety-relevant
 *   string. Inherited text already sitting near the AA floor would drop under
 *   it, so de-emphasis is left to the caller, which knows its own background.
 * - **No italic.** Persian script has no italic form; browsers synthesise an
 *   oblique that degrades Vazirmatn's letterforms.
 *
 * The meaning is carried by the word itself, not by styling — "نامشخص" is
 * unambiguous on its own, which is why it needs no visual marking to be read
 * correctly.
 */
export function UnknownField({ variant = "unknown", className }: UnknownFieldProps) {
  return (
    <span
      data-testid="unknown-field"
      data-missing={variant}
      className={cn("font-normal", className)}
    >
      {UNKNOWN_FIELD_TEXT[variant]}
    </span>
  );
}
