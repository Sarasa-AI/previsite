"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import DoctorLoginForm from "@/components/auth/DoctorLoginForm";
import { extractApiError } from "@/lib/api";

type MfaChallenge = {
  mode: "setup" | "verify";
  token: string;
  otpauthUri?: string;
};

export default function DoctorLoginPage() {
  const router = useRouter();
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null);
  const [code, setCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onMfaRequired = (payload: Record<string, unknown>) => {
    if (payload.mfa_setup_required === true && typeof payload.setup_token === "string") {
      setChallenge({
        mode: "setup",
        token: payload.setup_token,
        otpauthUri: typeof payload.otpauth_uri === "string" ? payload.otpauth_uri : undefined,
      });
      setError("");
      return;
    }
    if (payload.mfa_required === true && typeof payload.mfa_token === "string") {
      setChallenge({ mode: "verify", token: payload.mfa_token });
      setError("");
    }
  };

  const submitMfa = async (event: FormEvent) => {
    event.preventDefault();
    if (!challenge) return;
    setLoading(true);
    setError("");

    const endpoint =
      challenge.mode === "setup" ? "/api/auth/mfa/setup/verify" : "/api/auth/mfa/verify";
    const body =
      challenge.mode === "setup"
        ? { setup_token: challenge.token, code }
        : { mfa_token: challenge.token, code };

    let res: Response;
    try {
      res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch {
      setLoading(false);
      setError("ارتباط با سرور برقرار نشد");
      return;
    }

    const data = (await res.json().catch(() => null)) as Record<string, unknown> | null;
    setLoading(false);

    if (!res.ok) {
      setError(extractApiError(data, "کد تأیید نامعتبر است"));
      return;
    }

    if (challenge.mode === "setup" && Array.isArray(data?.backup_codes)) {
      setBackupCodes(data.backup_codes.map(String));
      return;
    }

    router.push("/doctor-dashboard");
  };

  if (backupCodes) {
    return (
      <main className="page-container flex min-h-screen items-center justify-center">
        <div className="medical-card w-full max-w-md space-y-4">
          <h2 className="text-xl font-bold text-slate-800">کدهای پشتیبان MFA</h2>
          <p className="text-sm text-slate-600">
            این کدها فقط یک‌بار نمایش داده می‌شوند. آن‌ها را در جای امن ذخیره کنید.
          </p>
          <ul className="grid grid-cols-2 gap-2 font-mono text-sm">
            {backupCodes.map((item) => (
              <li key={item} className="rounded-lg bg-slate-100 px-3 py-2 text-center">
                {item}
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="primary-button w-full"
            onClick={() => router.push("/doctor-dashboard")}
          >
            ورود به داشبورد
          </button>
        </div>
      </main>
    );
  }

  if (challenge) {
    return (
      <main className="page-container flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-4">
          <button
            type="button"
            className="inline-flex items-center gap-2 text-sm text-slate-600"
            onClick={() => setChallenge(null)}
          >
            <ArrowLeft className="h-4 w-4" />
            بازگشت
          </button>
          <form className="medical-card space-y-4" onSubmit={submitMfa}>
            <h2 className="text-2xl font-bold text-slate-800">
              {challenge.mode === "setup" ? "فعال‌سازی تأیید دو مرحله‌ای" : "کد تأیید دو مرحله‌ای"}
            </h2>
            {challenge.mode === "setup" && challenge.otpauthUri ? (
              <div className="space-y-2 text-sm text-slate-600">
                <p>URI سازگار با Google Authenticator:</p>
                <code className="block break-all rounded-lg bg-slate-100 p-3 text-xs">
                  {challenge.otpauthUri}
                </code>
                <p>پس از افزودن در اپلیکیشن Authenticator، کد ۶ رقمی را وارد کنید.</p>
              </div>
            ) : (
              <p className="text-sm text-slate-600">
                کد یک‌بارمصرف Authenticator یا یکی از کدهای پشتیبان را وارد کنید.
              </p>
            )}
            <input
              className="field-input"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="کد ۶ رقمی یا backup"
              required
              aria-label="کد MFA"
            />
            {error && (
              <p className="text-sm text-red-600" role="alert">
                {error}
              </p>
            )}
            <button className="primary-button w-full" disabled={loading} type="submit">
              {loading ? "در حال بررسی..." : "تأیید"}
            </button>
          </form>
        </div>
      </main>
    );
  }

  return (
    <main className="page-container flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-8">
          <ArrowLeft className="h-4 w-4" />
          بازگشت
        </Link>
        <DoctorLoginForm
          onSuccess={() => router.push("/doctor-dashboard")}
          onMfaRequired={onMfaRequired}
        />
      </div>
    </main>
  );
}
