"use client";

import { Radar, RefreshCcw } from "lucide-react";

export type ChatMessageItem = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  status?: "sent" | "sending" | "failed";
  createdAt?: string;
};

type ChatMessageProps = {
  message: ChatMessageItem;
  onRetry?: (id: number | string) => void;
};

// نکته آموزشی:
// `use client` فقط روی خود حباب پیام آمده چون شنود رویداد آفلاین، Retry و state بصری
// در همین لایه نیاز است؛ این کار از client شدن کل درخت جلوگیری می‌کند.
export default function ChatMessage({ message, onRetry }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isFailed = message.status === "failed";
  const isSending = message.status === "sending";

  return (
    <article className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
      <div className="max-w-[85%] space-y-2">
        <div
          className={[
            "rounded-[24px] px-4 py-3 shadow-sm transition-all duration-300 ease-spring",
            isUser ? "bg-white text-slate-900" : "bg-mint/70 text-trust",
            isFailed ? "opacity-55 saturate-50" : "opacity-100",
          ].join(" ")}
        >
          <div className="mb-2 flex items-center justify-between gap-3 text-xs font-semibold">
            <span className={isUser ? "text-trust" : "text-trust/80"}>{isUser ? "بیمار" : "دستیار"}</span>
            {isFailed ? (
              <span className="inline-flex items-center gap-1 text-red-600">
                <Radar className="h-4 w-4 animate-blink" />
                آفلاین
              </span>
            ) : isSending ? (
              <span className="text-slate-400">در حال ارسال...</span>
            ) : null}
          </div>
          <p className="whitespace-pre-wrap text-sm leading-7">{message.content}</p>
        </div>

        {isFailed && onRetry ? (
          <button
            className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold text-trust transition-colors duration-300 hover:bg-trust/5"
            type="button"
            onClick={() => onRetry(message.id)}
          >
            <RefreshCcw className="h-3.5 w-3.5" />
            تلاش مجدد
          </button>
        ) : null}
      </div>
    </article>
  );
}
