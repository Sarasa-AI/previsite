"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import { extractApiError } from "@/lib/api";
import { mapAuthError } from "@/lib/national-id";

type PatientLoginFormProps = {
  onSuccess: () => void;
};

export default function PatientLoginForm({ onSuccess }: PatientLoginFormProps) {
  const [nationalId, setNationalId] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    let res: Response;
    try {
      res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ national_id: nationalId, password }),
      });
    } catch {
      setLoading(false);
      setError("ارتباط با سرور برقرار نشد");
      return;
    }

    let data: unknown = null;
    try {
      const text = await res.text();
      data = text ? (JSON.parse(text) as unknown) : null;
    } catch {
      data = null;
    }

    setLoading(false);

    if (!res.ok) {
      const detail =
        data && typeof data === "object" && "detail" in data && typeof (data as { detail: unknown }).detail === "string"
          ? (data as { detail: string }).detail
          : undefined;
      setError(mapAuthError(detail, extractApiError(data, "ورود ناموفق بود")));
      return;
    }
    onSuccess();
  };

  const onNationalIdChange = (e: ChangeEvent<HTMLInputElement>) => setNationalId(e.target.value);
  const onPasswordChange = (e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value);

  return (
    <form className="medical-card space-y-4" onSubmit={onSubmit}>
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800">ورود به عنوان بیمار</h2>
        <p className="text-sm text-slate-500 mt-2">کد ملی و رمز عبور خود را وارد کنید</p>
      </div>
      <input
        value={nationalId}
        onChange={onNationalIdChange}
        placeholder="کد ملی (۱۰ رقم)"
        className="field-input"
        pattern="\d{10}"
        maxLength={10}
        required
        aria-label="کد ملی"
      />
      <input
        value={password}
        onChange={onPasswordChange}
        type="password"
        placeholder="رمز عبور"
        className="field-input"
        required
        aria-label="رمز عبور"
      />
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
      <button disabled={loading} type="submit" className="primary-button w-full">
        {loading ? "در حال ورود..." : "ورود"}
      </button>
      <div className="text-center">
        <Link href="/register" className="text-sm text-trust hover:underline">
          حساب کاربری ندارید؟ ثبت‌نام کنید
        </Link>
      </div>
    </form>
  );
}
