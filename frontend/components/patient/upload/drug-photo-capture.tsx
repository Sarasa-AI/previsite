"use client";

import { PhotoCaptureField, type PhotoCaptureCopy } from "./photo-capture-field";

/**
 * Photos of the patient's medication boxes / strips, which the OCR pipeline
 * reads drug names and doses from.
 *
 * The copy asks for a legible photo and says why; it does not tell the patient
 * anything about the medication itself (§5.4).
 */

const COPY: PhotoCaptureCopy = {
  label: "عکس داروها",
  hint: "از جعبه یا نوار هر دارویی که مصرف می‌کنید یک عکس بگیرید.",
  guidance:
    "نام دارو و مقدار آن روی جعبه باید در عکس خوانا باشد. اگر نوشته تار است، عکس را دوباره بگیرید تا اطلاعات درست ثبت شود.",
  captureAction: "گرفتن عکس دارو",
  libraryAction: "انتخاب از گالری",
};

type DrugPhotoCaptureProps = {
  files: File[];
  onChange: (files: File[]) => void;
  maxFiles?: number;
  className?: string;
};

export function DrugPhotoCapture({
  files,
  onChange,
  maxFiles = 8,
  className,
}: DrugPhotoCaptureProps) {
  return (
    <PhotoCaptureField
      testId="drug-photo-capture"
      copy={COPY}
      files={files}
      onChange={onChange}
      maxFiles={maxFiles}
      className={className}
    />
  );
}
