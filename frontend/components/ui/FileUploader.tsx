"use client";

import { useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { CheckCircle2, FileText, UploadCloud, XCircle } from "lucide-react";
import { AxiosError } from "axios";
import { frontendApi } from "@/lib/client";
import { extractApiError } from "@/lib/api";

type FileUploaderProps = {
  sessionId: string;
};

type UploadResult = {
  filename: string;
  size: number;
  mime_type: string;
};

const MAX_FILE_SIZE = 10 * 1024 * 1024;

function formatFileSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(2)} MB`;
  }

  return `${Math.ceil(size / 1024)} KB`;
}

// نکته آموزشی:
// `use client` این‌جا لازم است چون Drag & Drop، progress و رویدادهای فایل کاملاً
// تعاملی‌اند. با این جداسازی، صفحه‌ی route می‌تواند نازک بماند و بار client کمتر شود.
export default function FileUploader({ sessionId }: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [isShaking, setIsShaking] = useState(false);

  const progressLabel = useMemo(() => `${Math.round(progress)}%`, [progress]);

  const triggerInvalidFeedback = (message: string) => {
    setError(message);
    setIsShaking(true);
    window.setTimeout(() => setIsShaking(false), 450);
  };

  const validateFile = (file: File) => {
    if (file.size > MAX_FILE_SIZE) {
      triggerInvalidFeedback("حجم فایل باید حداکثر ۱۰ مگابایت باشد.");
      return false;
    }

    setError("");
    return true;
  };

  const handleFile = (file: File | null) => {
    if (!file) return;
    if (!validateFile(file)) {
      setSelectedFile(null);
      setResult(null);
      return;
    }

    setSelectedFile(file);
    setResult(null);
  };

  const onDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setIsDragging(false);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    handleFile(event.dataTransfer.files?.[0] ?? null);
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFile(event.target.files?.[0] ?? null);
  };

  const uploadSelectedFile = async () => {
    if (!selectedFile) {
      triggerInvalidFeedback("ابتدا یک فایل انتخاب کنید.");
      return;
    }

    setIsUploading(true);
    setProgress(0);
    setError("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await frontendApi.uploadFile(sessionId, formData, (event) => {
        const total = event.total ?? selectedFile.size;
        const uploaded = event.loaded;
        // فرمول خواسته‌شده: P = (uploaded / total) * 100
        const percent = total > 0 ? (uploaded / total) * 100 : 0;
        setProgress(Math.min(percent, 100));
      });

      setResult(response.data);
      setProgress(100);
    } catch (uploadError) {
      const payload = uploadError instanceof AxiosError ? uploadError.response?.data : undefined;
      setError(extractApiError(payload, "آپلود فایل ناموفق بود."));
      setResult(null);
      setProgress(0);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="medical-card space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-trust">آپلودر فایل هوشمند</p>
          <h2 className="text-2xl font-bold text-slate-900">مدارک پزشکی جلسه #{sessionId}</h2>
        </div>
        <span className="status-chip bg-mint/45 text-trust">حداکثر حجم: 10MB</span>
      </div>

      <div
        className={[
          "relative overflow-hidden rounded-[28px] border-2 border-dashed bg-white/90 p-6 transition-all duration-300 ease-spring",
          isDragging ? "scale-[1.02] border-mint shadow-lg shadow-mint/25" : "border-slate-300",
          isShaking ? "animate-shakeX" : "",
        ].join(" ")}
        onDragEnter={onDragEnter}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <div className="pointer-events-none absolute inset-x-5 bottom-4 top-[58%] rounded-[24px] bg-slate-100/80" />
        <div
          className="liquid-meter pointer-events-none absolute inset-x-5 bottom-4 rounded-[24px] bg-gradient-to-t from-mint via-mint/85 to-mint/60 transition-all duration-300 ease-spring"
          style={{ height: `${Math.max(progress, selectedFile ? 10 : 0)}%` }}
        />

        <div className="relative z-10 flex min-h-[260px] flex-col items-center justify-center gap-4 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-trust/8 text-trust">
            <UploadCloud className="h-8 w-8" />
          </div>

          <div className="space-y-2">
            <h3 className="text-xl font-semibold text-slate-900">فایل را بکشید و اینجا رها کنید</h3>
            <p className="mx-auto max-w-xl text-sm leading-7 text-slate-500">
              با ورود فایل به ناحیه، کادر به رنگ سبز مینت تغییر می‌کند و کمی بزرگ می‌شود تا بازخورد بصری آرام و واضح ایجاد شود.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button className="primary-button" type="button" onClick={() => inputRef.current?.click()}>
              انتخاب فایل
            </button>
            <button className="secondary-button" type="button" onClick={uploadSelectedFile} disabled={isUploading}>
              {isUploading ? `در حال آپلود ${progressLabel}` : "شروع آپلود"}
            </button>
          </div>

          <input ref={inputRef} className="hidden" type="file" onChange={onFileChange} />

          {selectedFile ? (
            <div className="flex w-full max-w-xl items-center gap-3 rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-right shadow-sm">
              <FileText className="h-5 w-5 shrink-0 text-trust" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900">{selectedFile.name}</p>
                <p className="text-xs text-slate-500">{formatFileSize(selectedFile.size)}</p>
              </div>
              <span className="text-sm font-semibold text-trust">{progressLabel}</span>
            </div>
          ) : null}
        </div>
      </div>

      {error ? (
        <p className="flex items-center gap-2 text-sm text-red-600 opacity-0 animate-fadeIn">
          <XCircle className="h-4 w-4" />
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="rounded-2xl border border-mint/70 bg-mint/30 p-4">
          <div className="flex items-center gap-2 text-trust">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-semibold">آپلود با موفقیت انجام شد</span>
          </div>
          <p className="mt-2 text-sm text-slate-700">
            فایل <span className="font-semibold">{result.filename}</span> با حجم {formatFileSize(result.size)} ثبت شد.
          </p>
        </div>
      ) : null}
    </section>
  );
}
