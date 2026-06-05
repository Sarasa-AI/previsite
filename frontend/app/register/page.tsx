"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { extractApiError } from "@/lib/api";

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    if (password !== confirmPassword) {
      setError("رمز عبور و تکرار آن مطابقت ندارند");
      setLoading(false);
      return;
    }

    let res: Response;
    try {
      res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          role: "patient",
        }),
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
      setError(extractApiError(data, "ثبت‌نام ناموفق بود"));
      return;
    }
    router.push("/login");
  };

  const onNameChange = (e: ChangeEvent<HTMLInputElement>) => setFullName(e.target.value);
  const onEmailChange = (e: ChangeEvent<HTMLInputElement>) => setEmail(e.target.value);
  const onPasswordChange = (e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value);
  const onConfirmPasswordChange = (e: ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value);

  return (
    <main className="page-container flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md">
        <Link href="/patient-select" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-8">
          <ArrowLeft className="h-4 w-4" />
          بازگشت
        </Link>
        <form className="medical-card space-y-4" onSubmit={onSubmit}>
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-slate-800">ثبت‌نام بیمار</h2>
            <p className="text-sm text-slate-500 mt-2">اطلاعات خود را وارد کنید</p>
          </div>
          <input
            value={fullName}
            onChange={onNameChange}
            placeholder="نام کامل"
            className="field-input"
            required
          />
          <input
            value={email}
            onChange={onEmailChange}
            type="email"
            placeholder="ایمیل"
            className="field-input"
            required
          />
          <input
            value={password}
            onChange={onPasswordChange}
            type="password"
            placeholder="رمز عبور"
            className="field-input"
            minLength={8}
            required
          />
          <input
            value={confirmPassword}
            onChange={onConfirmPasswordChange}
            type="password"
            placeholder="تکرار رمز عبور"
            className="field-input"
            minLength={8}
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button disabled={loading} type="submit" className="primary-button w-full">
            {loading ? "در حال ثبت..." : "ثبت‌نام"}
          </button>
          <div className="text-center">
            <Link href="/login" className="text-sm text-trust hover:underline">
              قبلاً ثبت‌نام کرده‌اید؟ وارد شوید
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}
