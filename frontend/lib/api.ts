import axios, { AxiosError } from "axios";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// نکته آموزشی:
// این فایل عمداً در لایه‌ی کلاینت نگه داشته شده است تا `use client` فقط در
// پایین‌ترین سطح تعاملی مصرف شود. صفحه‌ها لازم نیست هر بار منطق 401 را تکرار کنند.
// با interceptor می‌توان مدیریت خطا و در آینده Refresh Token را به‌صورت متمرکز افزود.
export const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      try {
        await fetch("/api/auth/logout", { method: "POST" });
      } catch {
        // اگر logout شکست بخورد، باز هم redirect ایمن انجام می‌دهیم.
      }

      const currentPath = window.location.pathname + window.location.search;
      window.location.href = `/login?next=${encodeURIComponent(currentPath)}`;
    }

    let errorMessage = "خطای ناشناخته رخ داده است";
    if (error.response) {
      const status = error.response.status;
      if (status === 422) {
        errorMessage = "اطلاعات وارد شده معتبر نیست. لطفاً بررسی کنید";
      } else if (status === 503) {
        errorMessage = "سرویس در دسترس نیست. لطفاً دوباره تلاش کنید";
      } else if (status >= 400 && status < 500) {
        const detail = extractApiError(error.response.data, "درخواست نامعتبر است");
        errorMessage = detail;
      } else if (status >= 500) {
        errorMessage = "خطای سرور رخ داده است. لطفاً بعداً تلاش کنید";
      }
    } else if (error.request) {
      errorMessage = "ارتباط با سرور برقرار نشد. لطفاً اینترنت خود را بررسی کنید";
    }

    return Promise.reject(new ApiError(errorMessage, error.response?.status));
  },
);

export function extractApiError(payload: unknown, fallbackMessage: string): string {
  if (payload && typeof payload === "object") {
    const response = payload as {
      detail?: unknown;
      error?: { message?: unknown };
      message?: unknown;
    };

    if (typeof response.detail === "string" && response.detail.trim()) {
      return response.detail;
    }

    if (typeof response.error?.message === "string" && response.error.message.trim()) {
      return response.error.message;
    }

    if (typeof response.message === "string" && response.message.trim()) {
      return response.message;
    }
  }

  return fallbackMessage;
}

export type SessionResponse = {
  id: number;
  patient_id: number;
  patient_name?: string | null;
  status: string;
  initial_complaint: string;
  created_at: string;
  progress: number;
};

export type MessageResponse = {
  id: number;
  session_id: number;
  role: string;
  content: string;
  created_at: string;
};
