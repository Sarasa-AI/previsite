"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import PatientLoginForm from "@/components/auth/PatientLoginForm";

export default function RegisterPage() {
  const router = useRouter();

  return (
    <main className="page-container flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md">
        <Link
          href="/patient-select"
          className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-8"
        >
          <ArrowLeft className="h-4 w-4" />
          بازگشت
        </Link>
        <PatientLoginForm
          mode="register"
          onSuccess={() => router.push("/dashboard")}
        />
      </div>
    </main>
  );
}
