"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { Activity, WifiOff, CheckCircle2 } from "lucide-react";
import ChatMessage, { type ChatMessageItem } from "@/components/chat/ChatMessage";
import ProtectedRoute from "@/components/ProtectedRoute";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";

type ApiMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

function mapServerMessages(messages: ApiMessage[]): ChatMessageItem[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    status: "sent",
  }));
}

function buildTempMessage(content: string): ChatMessageItem {
  return {
    id: `temp-${Date.now()}`,
    role: "user",
    content,
    status: "sending",
    createdAt: new Date().toISOString(),
  };
}

export default function ChatPage({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId;
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [session, setSession] = useState<any>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [online, setOnline] = useState(true);

  const hasFailedMessage = useMemo(() => messages.some((message) => message.status === "failed"), [messages]);

  const isInterviewComplete = useMemo(() => {
    return messages.some(m => m.role === "assistant" && m.content.includes("اطلاعات کافی جمع‌آوری شد"));
  }, [messages]);

  const markPendingAsFailed = useCallback(() => {
    setMessages((current) => {
      const pendingIndex = [...current].reverse().findIndex((message) => message.status === "sending");
      if (pendingIndex === -1) return current;
      const actualIndex = current.length - 1 - pendingIndex;
      return current.map((message, index) =>
        index === actualIndex ? { ...message, status: "failed" as const } : message,
      );
    });
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const response = await frontendApi.chatHistory(sessionId);
      setMessages(mapServerMessages(response.data.messages || []));
      setSession(response.data.session);
      setError("");
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "دریافت تاریخچه گفتگو ناموفق بود."));
    }
  }, [sessionId]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    const updateOnlineStatus = () => setOnline(window.navigator.onLine);
    const handleOffline = () => {
      setOnline(false);
      markPendingAsFailed();
    };
    const handleOnline = () => setOnline(true);

    updateOnlineStatus();
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, [markPendingAsFailed]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    const startTop = container.scrollTop;
    const targetTop = container.scrollHeight - container.clientHeight;
    const distance = targetTop - startTop;
    if (distance <= 0) return;

    let frameId = 0;
    const start = performance.now();
    const initialVelocity = Math.max(distance * 0.12, 32);

    const animate = (now: number) => {
      const elapsedSeconds = (now - start) / 1000;
      const decay = Math.exp(-0.5 * elapsedSeconds);
      const traveled = distance - initialVelocity * decay;
      container.scrollTop = Math.min(targetTop, startTop + Math.max(0, traveled));

      if (container.scrollTop < targetTop - 1) {
        frameId = window.requestAnimationFrame(animate);
      }
    };

    frameId = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frameId);
  }, [messages]);

  const submitMessage = useCallback(
    async (messageText: string) => {
      const trimmed = messageText.trim();
      if (!trimmed) return;

      const tempMessage = buildTempMessage(trimmed);
      setMessages((current) => [...current, tempMessage]);
      setLoading(true);
      setError("");

      if (!window.navigator.onLine) {
        setMessages((current) =>
          current.map((message) => (message.id === tempMessage.id ? { ...message, status: "failed" } : message)),
        );
        setLoading(false);
        return;
      }

      try {
        await frontendApi.sendMessage(sessionId, { content: trimmed });
        setContent("");
        await loadHistory();
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        const fallback = window.navigator.onLine ? "ارسال پیام ناموفق بود." : "اتصال اینترنت قطع شده است.";
        setError(extractApiError(payload, fallback));
        setMessages((current) =>
          current.map((message) => (message.id === tempMessage.id ? { ...message, status: "failed" } : message)),
        );
      } finally {
        setLoading(false);
      }
    },
    [loadHistory, sessionId],
  );

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await submitMessage(content);
  };

  const retryMessage = async (id: number | string) => {
    const retryTarget = messages.find((message) => message.id === id);
    if (!retryTarget) return;

    setMessages((current) => current.filter((message) => message.id !== id));
    await submitMessage(retryTarget.content);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    try {
      await frontendApi.submitSession(sessionId);
      await loadHistory();
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "ثبت نهایی ناموفق بود."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ProtectedRoute>
      <main className="page-container grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
        <section className="medical-card flex min-h-[72vh] flex-col">
          <div className="mb-4 flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-trust">سیستم چت ضد-قطعی</p>
              <h1 className="text-2xl font-bold text-slate-900">مصاحبه پزشکی جلسه #{sessionId}</h1>
            </div>
            <div className="flex items-center gap-2">
              {session?.status === "pending_review" && (
                <span className="status-chip bg-amber-100 text-amber-700">در انتظار بررسی پزشک</span>
              )}
              <span className={`status-chip ${online ? "bg-mint/45 text-trust" : "bg-red-50 text-red-600"}`}>
                {online ? <Activity className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
                {online ? "آنلاین" : "آفلاین"}
              </span>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto rounded-[28px] bg-slate-50/70 p-4">
            {messages.length ? (
              messages.map((message) => <ChatMessage key={message.id} message={message} onRetry={retryMessage} />)
            ) : (
              <div className="flex h-full min-h-[240px] items-center justify-center text-center text-sm text-slate-500">
                هنوز پیامی ثبت نشده است. گفتگو را با شرح حال بیمار شروع کنید.
              </div>
            )}
          </div>

          {session?.status === "active" ? (
            <form className="mt-4 space-y-3" onSubmit={sendMessage}>
              {isInterviewComplete && (
                <div className="mb-4 rounded-2xl border border-trust/20 bg-trust/5 p-4 text-center">
                  <p className="mb-3 text-sm font-semibold text-trust">تمام مراحل با موفقیت انجام شد. اکنون می‌توانید پرونده را برای پزشک ارسال کنید.</p>
                  <button 
                    type="button" 
                    className="primary-button mx-auto w-full sm:w-auto"
                    onClick={handleSubmit}
                    disabled={submitting}
                  >
                    {submitting ? "در حال ارسال..." : "تایید و ارسال شرح حال به پزشک"}
                  </button>
                </div>
              )}
              <textarea
                className="field-input min-h-[120px] resize-none"
                value={content}
                onChange={(event) => setContent(event.target.value)}
                placeholder="شرح حال، علائم یا سوال بیمار را وارد کنید..."
                rows={4}
                required
                disabled={isInterviewComplete}
              />
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm text-slate-500">
                  {hasFailedMessage ? "آخرین پیام ناموفق کم‌رنگ شده و امکان Retry دارد." : "پیام‌ها بدون پاپ‌آپ مزاحم مدیریت می‌شوند."}
                </div>
                <button className="primary-button sm:w-auto" disabled={loading || isInterviewComplete} type="submit">
                  {loading ? "در حال ارسال..." : "ارسال پیام"}
                </button>
              </div>
            </form>
          ) : (
            <div className="mt-6 rounded-2xl bg-mint/10 p-6 text-center">
              <CheckCircle2 className="mx-auto h-12 w-12 text-trust mb-3" />
              <h3 className="text-lg font-bold text-slate-900">پرونده با موفقیت ارسال شد</h3>
              <p className="text-sm text-slate-600 mt-2">شرح حال شما برای پزشک ارسال شده و در انتظار بررسی است.</p>
            </div>
          )}
          {error ? <p className="text-sm text-red-600 mt-2">{error}</p> : null}
        </section>

        <aside className="medical-card space-y-4">
          <div>
            <p className="text-sm font-semibold text-trust">راهنمای تجربه کاربر</p>
            <h2 className="text-xl font-bold text-slate-900">پاسخ نرم در شرایط ناپایدار شبکه</h2>
          </div>
          <ul className="space-y-3 text-sm leading-7 text-slate-600">
            <li>قطع اینترنت فقط روی آخرین پیامِ در حال ارسال اثر می‌گذارد و همان پیام کم‌رنگ می‌شود.</li>
            <li>آیکون رادار قرمز به‌صورت چشمک‌زن دیده می‌شود تا مشکل شبکه بی‌سروصدا اما واضح منتقل شود.</li>
            <li>اسکرول به انتهای چت با تابع میرایی نمایی انجام می‌شود تا پرش ناگهانی رخ ندهد.</li>
          </ul>
        </aside>
      </main>
    </ProtectedRoute>
  );
}
