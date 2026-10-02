import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Call BFF refresh exactly once (shared across concurrent 401s).
 * Returns true when new cookies were set.
 */
async function refreshSessionOnce(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const response = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      return response.ok;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

async function clearSessionAndRedirect(): Promise<void> {
  try {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
  } catch {
    // Redirect regardless of logout outcome.
  }
  if (typeof window !== "undefined") {
    const currentPath = window.location.pathname + window.location.search;
    window.location.href = `/login?next=${encodeURIComponent(currentPath)}`;
  }
}

// نکته آموزشی:
// این فایل عمداً در لایه‌ی کلاینت نگه داشته شده است تا `use client` فقط در
// پایین‌ترین سطح تعاملی مصرف شود. صفحه‌ها لازم نیست هر بار منطق 401 را تکرار کنند.
// با interceptor: یک‌بار refresh و یک retry؛ بدون حلقهٔ refresh.
export const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;

    if (
      error.response?.status === 401 &&
      typeof window !== "undefined" &&
      config &&
      !config._retry
    ) {
      config._retry = true;
      const refreshed = await refreshSessionOnce();
      if (refreshed) {
        return apiClient.request(config);
      }
      await clearSessionAndRedirect();
    } else if (
      error.response?.status === 401 &&
      typeof window !== "undefined" &&
      config?._retry
    ) {
      await clearSessionAndRedirect();
    }

    let errorMessage = "خطای ناشناخته رخ داده است";
    if (error.response) {
      const status = error.response.status;
      if (status === 422) {
        errorMessage = "اطلاعات وارد شده معتبر نیست. لطفاً بررسی کنید";
      } else if (status === 503) {
        errorMessage = extractApiError(
          error.response.data,
          "سرویس در دسترس نیست. لطفاً دوباره تلاش کنید",
        );
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

    if (response.detail && typeof response.detail === "object") {
      const detail = response.detail as {
        message?: unknown;
        code?: unknown;
        missing?: unknown;
      };
      if (typeof detail.message === "string" && detail.message.trim()) {
        return detail.message;
      }
      if (detail.code === "CONSENT_REQUIRED") {
        const missing = Array.isArray(detail.missing)
          ? detail.missing.filter((k): k is string => typeof k === "string")
          : [];
        return missing.length
          ? `CONSENT_REQUIRED:${missing.join(",")}`
          : "CONSENT_REQUIRED";
      }
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

export type ConsentRequiredDetail = {
  code: "CONSENT_REQUIRED";
  missing: string[];
};

export function parseConsentRequiredDetail(
  payload: unknown,
): ConsentRequiredDetail | null {
  if (!payload || typeof payload !== "object") return null;
  const detail = (payload as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const body = detail as { code?: unknown; missing?: unknown };
  if (body.code !== "CONSENT_REQUIRED") return null;
  const missing = Array.isArray(body.missing)
    ? body.missing.filter((k): k is string => typeof k === "string")
    : [];
  return { code: "CONSENT_REQUIRED", missing };
}

export function isConsentRequiredError(payload: unknown): boolean {
  return parseConsentRequiredDetail(payload) !== null;
}

export type ConsentStatusItem = {
  consent_key: string;
  policy_version: string;
  copy_text_key: string;
  granted: boolean;
  granted_at?: string | null;
  withdrawn_at?: string | null;
  latest_record_id?: number | null;
  latest_policy_version?: string | null;
};

export type ConsentStatusResponse = {
  enforcement_enabled: boolean;
  required_for_processing: string[];
  consents: ConsentStatusItem[];
};

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
