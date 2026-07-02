"use client";

import { useMemo, useRef, useState, type ChangeEvent } from "react";
import { AxiosError } from "axios";
import { FileText, Loader2, RotateCcw, X } from "lucide-react";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import type { ConditionFile } from "@/lib/pmh/types";

const MAX_FILE_SIZE = 10 * 1024 * 1024;

type InlineConditionUploadProps = {
  sessionId: string;
  conditionId: string;
  file: ConditionFile | null;
  onFileChange: (conditionId: string, file: ConditionFile | null) => void;
  disabled?: boolean;
};

type UploadResponse = {
  id: number;
  filename: string;
  size: number;
  mime_type: string;
  condition_id: string | null;
};

function toConditionFile(data: UploadResponse): ConditionFile {
  return {
    id: data.id,
    filename: data.filename,
    size: data.size,
    mime_type: data.mime_type,
    condition_id: data.condition_id,
    url: `/api/files/download/${data.id}`,
  };
}

export function InlineConditionUpload({
  sessionId,
  conditionId,
  file,
  onFileChange,
  disabled,
}: InlineConditionUploadProps) {
  const inputId = useMemo(() => `condition-upload-${crypto.randomUUID()}`, []);
  const inputRef = useRef<HTMLInputElement>(null);
  const lastSelectedFileRef = useRef<File | null>(null);
  const pendingUnlinkRef = useRef<ConditionFile | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isUnlinking, setIsUnlinking] = useState(false);
  const [error, setError] = useState("");
  const [errorKind, setErrorKind] = useState<"upload" | "unlink" | null>(null);

  const isBusy = isUploading || isUnlinking;
  const slotDisabled = disabled || isBusy;

  const uploadSelectedFile = async (selectedFile: File) => {
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError("حجم فایل باید حداکثر ۱۰ مگابایت باشد.");
      setErrorKind("upload");
      return;
    }

    setIsUploading(true);
    setError("");
    setErrorKind(null);
    lastSelectedFileRef.current = selectedFile;

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await frontendApi.uploadFile(sessionId, formData, undefined, conditionId);
      onFileChange(conditionId, toConditionFile(response.data as UploadResponse));
    } catch (uploadError) {
      const payload = uploadError instanceof AxiosError ? uploadError.response?.data : undefined;
      setError(extractApiError(payload, "آپلود فایل ناموفق بود."));
      setErrorKind("upload");
    } finally {
      setIsUploading(false);
    }
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    event.target.value = "";
    if (!selected || slotDisabled) return;
    void uploadSelectedFile(selected);
  };

  const handleRemove = async () => {
    if (!file || slotDisabled) return;

    pendingUnlinkRef.current = file;
    setError("");
    setErrorKind(null);
    onFileChange(conditionId, null);
    setIsUnlinking(true);

    try {
      await frontendApi.unlinkFile(sessionId, file.id);
      pendingUnlinkRef.current = null;
    } catch (unlinkError) {
      const snapshot = pendingUnlinkRef.current;
      if (snapshot) {
        onFileChange(conditionId, snapshot);
      }
      const payload = unlinkError instanceof AxiosError ? unlinkError.response?.data : undefined;
      setError(extractApiError(payload, "حذف فایل ناموفق بود."));
      setErrorKind("unlink");
    } finally {
      setIsUnlinking(false);
    }
  };

  const handleRetry = () => {
    if (errorKind === "upload" && lastSelectedFileRef.current) {
      void uploadSelectedFile(lastSelectedFileRef.current);
      return;
    }

    if (errorKind === "unlink" && file) {
      void handleRemove();
      return;
    }

    inputRef.current?.click();
  };

  const openPicker = () => {
    if (slotDisabled) return;
    if (error) {
      handleRetry();
      return;
    }
    inputRef.current?.click();
  };

  if (isUploading) {
    return (
      <div className="flex min-h-10 min-w-[120px] items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-white px-2 text-xs text-slate-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>در حال آپلود...</span>
      </div>
    );
  }

  if (file) {
    return (
      <div
        className={[
          "flex min-h-10 min-w-[120px] max-w-[160px] items-center gap-1.5 rounded-full border px-2 py-1",
          error ? "border-red-400 bg-red-50" : "border-mint/70 bg-mint/25 text-trust",
        ].join(" ")}
      >
        <FileText className="h-3.5 w-3.5 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-xs font-medium" title={file.filename}>
          {file.filename}
        </span>
        {error ? (
          <button
            type="button"
            onClick={handleRetry}
            className="shrink-0 rounded-full p-0.5 text-red-600 hover:bg-red-100"
            aria-label="تلاش مجدد"
            disabled={disabled || isUnlinking}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void handleRemove()}
            className="shrink-0 rounded-full p-0.5 text-slate-500 hover:bg-white/60 hover:text-red-600"
            aria-label="حذف فایل"
            disabled={slotDisabled}
          >
            {isUnlinking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <X className="h-3.5 w-3.5" />}
          </button>
        )}
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          className="hidden"
          onChange={handleInputChange}
          disabled={slotDisabled}
        />
      </div>
    );
  }

  return (
    <div className="min-w-[120px]">
      <button
        type="button"
        onClick={openPicker}
        disabled={slotDisabled}
        className={[
          "flex min-h-10 w-full items-center justify-center rounded-xl border border-dashed px-2 text-xs transition-colors",
          error
            ? "border-red-400 bg-red-50 text-red-600"
            : "border-slate-300 text-slate-400 hover:border-trust/40 hover:text-trust",
          slotDisabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
        ].join(" ")}
      >
        {error ? (
          <span className="flex items-center gap-1.5">
            <RotateCcw className="h-3.5 w-3.5" />
            تلاش مجدد
          </span>
        ) : (
          "آپلود"
        )}
      </button>
      {error ? (
        <p className="mt-1 text-[10px] leading-tight text-red-600">{error}</p>
      ) : null}
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        className="hidden"
        onChange={handleInputChange}
        disabled={slotDisabled}
      />
    </div>
  );
}
