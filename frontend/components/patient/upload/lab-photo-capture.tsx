"use client";

import { PhotoCaptureField, type PhotoCaptureCopy } from "./photo-capture-field";

/**
 * Photos of printed lab reports. Higher file-size ceiling than the drug field —
 * a full A4 sheet needs more resolution than a medication box before the
 * numeric columns stop being legible to OCR.
 *
 * The copy explains what must be readable and nothing more: no reference
 * ranges, no interpretation of any result (§5.4).
 */

const COPY: PhotoCaptureCopy = {
  label: "عکس برگه‌های آزمایش",
  hint: "از هر برگه آزمایش، یک عکس کامل و صاف بگیرید.",
  guidance:
    "تمام برگه در کادر عکس باشد و نام آزمایش‌ها و عددها خوانا باشد. عکس را در نور کافی و بدون سایه بگیرید.",
  captureAction: "گرفتن عکس برگه",
  libraryAction: "انتخاب از گالری",
};

type LabPhotoCaptureProps = {
  files: File[];
  onChange: (files: File[]) => void;
  maxFiles?: number;
  className?: string;
};

export function LabPhotoCapture({
  files,
  onChange,
  maxFiles = 10,
  className,
}: LabPhotoCaptureProps) {
  return (
    <PhotoCaptureField
      testId="lab-photo-capture"
      copy={COPY}
      files={files}
      onChange={onChange}
      maxFiles={maxFiles}
      maxFileSizeMb={12}
      className={className}
    />
  );
}
