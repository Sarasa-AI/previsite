import Link from "next/link";
import { ArrowLeft, Check, X } from "lucide-react";

export default function PatientSelectPage() {
  return (
    <main className="page-container flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-8">
          <ArrowLeft className="h-4 w-4" />
          بازگشت
        </Link>
        <div className="medical-card space-y-6">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-slate-800">آیا قبلاً ثبت‌نام کرده‌اید؟</h2>
          </div>
          <div className="grid gap-4">
            <Link href="/login">
              <div className="border-2 border-slate-200 rounded-2xl p-6 flex items-center gap-4 hover:border-trust hover:bg-trust/5 cursor-pointer transition-all">
                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <Check className="w-6 h-6 text-green-700" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-800">بله، وارد شوید</h3>
                  <p className="text-sm text-slate-500">حساب کاربری دارم</p>
                </div>
              </div>
            </Link>
            <Link href="/register">
              <div className="border-2 border-slate-200 rounded-2xl p-6 flex items-center gap-4 hover:border-mint hover:bg-mint/20 cursor-pointer transition-all">
                <div className="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center">
                  <X className="w-6 h-6 text-orange-700" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-800">خیر، ثبت‌نام کنید</h3>
                  <p className="text-sm text-slate-500">حساب کاربری جدید بسازید</p>
                </div>
              </div>
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
