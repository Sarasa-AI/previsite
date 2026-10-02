"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { extractApiError } from "@/lib/api";
import { mapOtpError } from "@/lib/otp-errors";
import { normalizeIranianMobileClient, toAsciiDigits } from "@/lib/phone";

type PatientLoginFormProps = {
  onSuccess: () => void;
  /** When true, copy emphasizes first-time registration. */
  mode?: "login" | "register";
};

type Step = "phone" | "code";

export default function PatientLoginForm({
  onSuccess,
  mode = "login",
}: PatientLoginFormProps) {
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setInterval(() => {
      setCooldown((c) => (c > 0 ? c - 1 : 0));
    }, 1000);
    return () => window.clearInterval(id);
  }, [cooldown]);

  const requestOtp = async (rawPhone: string) => {
    const res = await fetch("/api/auth/otp/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        phone: normalizeIranianMobileClient(rawPhone),
      }),
    });
    const text = await res.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    if (!res.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data
          ? String((data as { detail: unknown }).detail)
          : undefined;
      throw new Error(
        mapOtpError(detail, extractApiError(data, "ارسال کد ناموفق بود")),
      );
    }
    const cooldownSeconds =
      data &&
      typeof data === "object" &&
      "cooldown_seconds" in data &&
      typeof (data as { cooldown_seconds: unknown }).cooldown_seconds === "number"
        ? (data as { cooldown_seconds: number }).cooldown_seconds
        : 60;
    setCooldown(cooldownSeconds);
  };

  const onRequest = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await requestOtp(phone);
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "ارسال کد ناموفق بود");
    } finally {
      setLoading(false);
    }
  };

  const onVerify = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: normalizeIranianMobileClient(phone),
          code: toAsciiDigits(code).trim(),
        }),
      });
      const text = await res.text();
      let data: unknown = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = null;
      }
      if (!res.ok) {
        const detail =
          data && typeof data === "object" && "detail" in data
            ? String((data as { detail: unknown }).detail)
            : undefined;
        setError(
          mapOtpError(detail, extractApiError(data, "تأیید کد ناموفق بود")),
        );
        return;
      }
      onSuccess();
    } catch {
      setError("ارتباط با سرور برقرار نشد");
    } finally {
      setLoading(false);
    }
  };

  const onResend = async () => {
    if (cooldown > 0 || loading) return;
    setLoading(true);
    setError("");
    try {
      await requestOtp(phone);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ارسال مجدد ناموفق بود");
    } finally {
      setLoading(false);
    }
  };

  const title = mode === "register" ? "ثبت‌نام بیمار" : "ورود به عنوان بیمار";
  const subtitle =
    step === "phone"
      ? "شماره موبایل خود را وارد کنید"
      : "کد پیامک‌شده را وارد کنید";

  if (step === "code") {
    return (
      <form className="medical-card space-y-4" onSubmit={onVerify}>
        <div className="text-center mb-6">
          <h2 className="text-2xl font-bold text-slate-800">{title}</h2>
          <p className="text-sm text-slate-500 mt-2">{subtitle}</p>
        </div>
        <input
          value={code}
          onChange={(e) => setCode(toAsciiDigits(e.target.value).slice(0, 6))}
          placeholder="کد ۶ رقمی"
          className="field-input"
          inputMode="numeric"
          maxLength={6}
          pattern="\d{6}"
          required
          aria-label="کد تأیید"
        />
        {error && (
          <p className="text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        <button disabled={loading} type="submit" className="primary-button w-full">
          {loading ? "در حال تأیید..." : "تأیید و ورود"}
        </button>
        <button
          type="button"
          className="w-full text-sm text-trust disabled:text-slate-400"
          disabled={cooldown > 0 || loading}
          onClick={onResend}
        >
          {cooldown > 0 ? `ارسال مجدد تا ${cooldown} ثانیه` : "ارسال مجدد کد"}
        </button>
        <button
          type="button"
          className="w-full text-sm text-slate-500"
          onClick={() => {
            setStep("phone");
            setCode("");
            setError("");
          }}
        >
          تغییر شماره
        </button>
      </form>
    );
  }

  return (
    <form className="medical-card space-y-4" onSubmit={onRequest}>
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800">{title}</h2>
        <p className="text-sm text-slate-500 mt-2">{subtitle}</p>
      </div>
      <input
        value={phone}
        onChange={(e) => setPhone(toAsciiDigits(e.target.value))}
        placeholder="۰۹۱۲۱۲۳۴۵۶۷"
        className="field-input"
        inputMode="tel"
        required
        aria-label="شماره موبایل"
      />
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
      <button disabled={loading} type="submit" className="primary-button w-full">
        {loading ? "در حال ارسال..." : "دریافت کد"}
      </button>
      <div className="text-center">
        {mode === "login" ? (
          <Link href="/register" className="text-sm text-trust hover:underline">
            حساب کاربری ندارید؟ ثبت‌نام کنید
          </Link>
        ) : (
          <Link href="/login" className="text-sm text-trust hover:underline">
            قبلاً ثبت‌نام کرده‌اید؟ وارد شوید
          </Link>
        )}
      </div>
    </form>
  );
}
