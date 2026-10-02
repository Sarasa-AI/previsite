"use client";

import { useState, type FormEvent } from "react";
import { extractApiError } from "@/lib/api";

type DoctorLoginFormProps = {
  onSuccess: () => void;
  /** Optional MFA step callback for future wiring; unused when MFA disabled. */
  onMfaRequired?: (payload: Record<string, unknown>) => void;
};

export default function DoctorLoginForm({ onSuccess, onMfaRequired }: DoctorLoginFormProps) {
  const [email, setEmail] = useState("");
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
        body: JSON.stringify({ email, password }),
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
      setError(extractApiError(data, "ایمیل یا رمز عبور اشتباه است"));
      return;
    }

    if (
      data &&
      typeof data === "object" &&
      ("mfa_required" in data || "mfa_setup_required" in data) &&
      onMfaRequired
    ) {
      onMfaRequired(data as Record<string, unknown>);
      return;
    }

    onSuccess();
  };

  return (
    <form className="medical-card space-y-4" onSubmit={onSubmit}>
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800">ورود به عنوان پزشک</h2>
        <p className="text-sm text-slate-500 mt-2">ایمیل و رمز عبور خود را وارد کنید</p>
      </div>
      <input
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        type="email"
        placeholder="ایمیل"
        className="field-input"
        required
        aria-label="ایمیل"
      />
      <input
        value={password}
        onChange={(e) => setPassword(e.target.value)}
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
    </form>
  );
}
