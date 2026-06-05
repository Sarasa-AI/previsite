import Link from "next/link";
import { Stethoscope, User } from "lucide-react";

export default function HomePage() {
  return (
    <main className="page-container flex min-h-screen items-center justify-center">
      <div className="w-full max-w-3xl">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-trust mb-4">PreVisit</h1>
          <p className="text-lg text-slate-600">سیستم مصاحبه پزشکی هوشمند پیش از ویزیت</p>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <Link href="/doctor-login">
            <div className="medical-card flex flex-col items-center justify-center gap-4 p-8 hover:border-trust hover:shadow-xl cursor-pointer transition-all duration-300">
              <div className="w-20 h-20 rounded-full bg-trust/10 flex items-center justify-center">
                <Stethoscope className="w-10 h-10 text-trust" />
              </div>
              <div className="text-center">
                <h2 className="text-xl font-bold text-slate-800">ورود به عنوان پزشک</h2>
                <p className="text-sm text-slate-500 mt-2">بررسی و مدیریت جلسات بیماران</p>
              </div>
            </div>
          </Link>
          <Link href="/patient-select">
            <div className="medical-card flex flex-col items-center justify-center gap-4 p-8 hover:border-mint hover:shadow-xl cursor-pointer transition-all duration-300">
              <div className="w-20 h-20 rounded-full bg-mint/30 flex items-center justify-center">
                <User className="w-10 h-10 text-trust" />
              </div>
              <div className="text-center">
                <h2 className="text-xl font-bold text-slate-800">ورود به عنوان بیمار</h2>
                <p className="text-sm text-slate-500 mt-2">ایجاد و تکمیل مصاحبه پزشکی</p>
              </div>
            </div>
          </Link>
        </div>
      </div>
    </main>
  );
}
