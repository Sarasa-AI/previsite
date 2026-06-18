"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { extractApiError } from "@/lib/api";

export default function DoctorLoginPage() {
  const [username, setUsername] = useState("bagherzade");
  const [password, setPassword] = useState("0808");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    let res: Response;
    try {
      res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: username, password }),
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
      setError(extractApiError(data, "نام کاربری یا رمز عبور اشتباه است"));
      return;
    }
    router.push("/doctor-dashboard");
  };

  return (
    <main className="page-container flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-8">
          <ArrowLeft className="h-4 w-4" />
          بازگشت
        </Link>
        <form className="medical-card space-y-4" onSubmit={onSubmit}>
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-slate-800">ورود به عنوان پزشک</h2>
            <p className="text-sm text-slate-500 mt-2">نام کاربری و رمز عبور خود را وارد کنید</p>
          </div>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="نام کاربری"
            className="field-input"
            required
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            placeholder="رمز عبور"
            className="field-input"
            required
          />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button disabled={loading} type="submit" className="primary-button w-full">
            {loading ? "در حال ورود..." : "ورود"}
          </button>
        </form>
      </div>
    </main>
  );
}
