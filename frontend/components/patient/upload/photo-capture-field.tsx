"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { BidiText } from "@/components/shared/bidi-text";
import { cn } from "@/lib/utils";
import { AmberBox } from "../amber-box";

/**
 * Shared internals for the two patient photo-capture fields (drug boxes, lab
 * sheets). Both live on the patient side, so this holds patient tokens and is
 * *not* a `components/shared/**` component — §2's no-sharing rule is about
 * crossing the patient/clinician boundary, which this never does.
 *
 * Not exported from the wizard's public surface: callers use
 * <DrugPhotoCapture> / <LabPhotoCapture>, which supply the copy and the limits.
 */

const BYTES_PER_MB = 1024 * 1024;

/** Same curve as tailwind's `ease-spring` / the `--spring-easing` CSS var. */
const SPRING_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

/** Human-readable size. Latin digits by design — the caller wraps it in BidiText. */
function formatSize(bytes: number): string {
  const mb = bytes / BYTES_PER_MB;
  return mb >= 0.1 ? `${mb.toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export type PhotoCaptureCopy = {
  /** Field heading, e.g. "عکس داروها". */
  label: string;
  /** One plain sentence on what to photograph. */
  hint: string;
  /** Warning-box guidance — why the photo is needed / what must be legible. */
  guidance: ReactNode;
  /** Primary button, e.g. "گرفتن عکس دارو". */
  captureAction: string;
  /** Secondary button for an existing image. */
  libraryAction: string;
};

type PhotoCaptureFieldProps = {
  copy: PhotoCaptureCopy;
  /** Controlled: the wizard owns the file list so it survives step changes. */
  files: File[];
  onChange: (files: File[]) => void;
  maxFiles?: number;
  maxFileSizeMb?: number;
  className?: string;
  /** data-testid prefix so the two variants are distinguishable in tests. */
  testId: string;
};

export function PhotoCaptureField({
  copy,
  files,
  onChange,
  maxFiles = 5,
  maxFileSizeMb = 8,
  className,
  testId,
}: PhotoCaptureFieldProps) {
  const reduced = useReducedMotion() ?? false;
  const captureRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const headingId = useId();

  // Object URLs are created in an effect, never in render: createObjectURL is a
  // side effect with a matching revoke, and the server has no URL global.
  const [previews, setPreviews] = useState<string[]>([]);
  useEffect(() => {
    const urls = files.map((file) => URL.createObjectURL(file));
    setPreviews(urls);
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [files]);

  const remaining = Math.max(0, maxFiles - files.length);
  const atLimit = remaining === 0;

  function accept(incoming: FileList | null) {
    if (!incoming || incoming.length === 0) return;
    const candidates = Array.from(incoming);
    const tooBig = candidates.find((file) => file.size > maxFileSizeMb * BYTES_PER_MB);
    if (tooBig) {
      setError(`حجم عکس بیشتر از حد مجاز است. حداکثر ${maxFileSizeMb} مگابایت.`);
      return;
    }
    if (candidates.length > remaining) {
      setError(`حداکثر ${maxFiles} عکس می‌توانید اضافه کنید.`);
      return;
    }
    setError(null);
    onChange([...files, ...candidates]);
  }

  function removeAt(index: number) {
    setError(null);
    onChange(files.filter((_, i) => i !== index));
  }

  const inputClass = "sr-only";
  const buttonBase = cn(
    "inline-flex min-h-14 flex-1 items-center justify-center gap-2 rounded-2xl px-4",
    "text-base font-semibold transition-colors duration-200",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
    "disabled:cursor-not-allowed disabled:opacity-60",
  );

  return (
    <div
      data-testid={testId}
      className={cn("flex flex-col gap-4", className)}
      aria-labelledby={headingId}
      role="group"
    >
      <div>
        <p id={headingId} className="text-xl font-semibold leading-relaxed">
          {copy.label}
        </p>
        <p className="mt-1 text-base leading-relaxed text-slate-600">{copy.hint}</p>
      </div>

      <AmberBox>{copy.guidance}</AmberBox>

      {/* Two inputs rather than one: `capture` opens the camera directly, and a
          patient who already photographed the box needs the plain picker. */}
      <input
        ref={captureRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className={inputClass}
        onChange={(event) => {
          accept(event.target.files);
          event.target.value = "";
        }}
        tabIndex={-1}
        aria-hidden="true"
      />
      <input
        ref={libraryRef}
        type="file"
        accept="image/*"
        multiple
        className={inputClass}
        onChange={(event) => {
          accept(event.target.files);
          event.target.value = "";
        }}
        tabIndex={-1}
        aria-hidden="true"
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          disabled={atLimit}
          onClick={() => captureRef.current?.click()}
          className={cn(buttonBase, "bg-primary text-primary-foreground hover:bg-primary-hover")}
        >
          <CameraGlyph />
          {copy.captureAction}
        </button>
        <button
          type="button"
          disabled={atLimit}
          onClick={() => libraryRef.current?.click()}
          className={cn(
            buttonBase,
            "border border-primary/40 bg-white text-primary hover:bg-primary-surface",
          )}
        >
          {copy.libraryAction}
        </button>
      </div>

      {error ? (
        <p
          role="alert"
          data-testid={`${testId}-error`}
          className="rounded-2xl bg-critical-surface px-4 py-3 text-base font-medium text-critical"
        >
          {error}
        </p>
      ) : null}

      {/* §5.2 — an empty state is written out, never left as a blank region. */}
      {files.length === 0 ? (
        <p
          data-testid={`${testId}-empty`}
          className="rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-center text-base text-slate-500"
        >
          ثبت نشده
        </p>
      ) : (
        <ul className="flex flex-col gap-3" data-testid={`${testId}-list`}>
          <AnimatePresence initial={false}>
            {files.map((file, index) => (
              <motion.li
                key={`${file.name}-${file.lastModified}-${file.size}`}
                layout={!reduced}
                initial={reduced ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, y: -6 }}
                transition={reduced ? { duration: 0 } : { duration: 0.22, ease: SPRING_EASE }}
                className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3"
              >
                {previews[index] ? (
                  // eslint-disable-next-line @next/next/no-img-element -- blob: URL, next/image cannot optimize it
                  <img
                    src={previews[index]}
                    alt=""
                    className="h-14 w-14 shrink-0 rounded-xl object-cover"
                  />
                ) : (
                  <span
                    aria-hidden="true"
                    className="h-14 w-14 shrink-0 rounded-xl bg-primary-surface"
                  />
                )}

                <span className="min-w-0 flex-1 text-sm">
                  <BidiText className="block truncate font-medium">{file.name}</BidiText>
                  <BidiText className="block text-slate-500">{formatSize(file.size)}</BidiText>
                </span>

                <button
                  type="button"
                  onClick={() => removeAt(index)}
                  aria-label={`حذف عکس ${index + 1}`}
                  className={cn(
                    "grid h-14 w-14 shrink-0 place-items-center rounded-xl text-critical",
                    "transition-colors duration-200 hover:bg-critical-surface",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  )}
                >
                  <TrashGlyph />
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}

      <p className="text-sm text-slate-500">
        {atLimit
          ? `به حداکثر ${maxFiles} عکس رسیدید.`
          : `می‌توانید ${remaining} عکس دیگر اضافه کنید.`}
      </p>
    </div>
  );
}

function CameraGlyph() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-6 w-6"
    >
      <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  );
}

function TrashGlyph() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}
