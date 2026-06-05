"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { frontendApi } from "@/lib/client";

// نکته آموزشی:
// این لایه فقط برای اعتبارسنجی نهایی سمت کلاینت نگه داشته شده است. redirect اولیه
// را middleware انجام می‌دهد تا صفحه فلاش نخورد و `use client` به حداقل برسد.
export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const validateSession = async () => {
      try {
        const response = await frontendApi.listSessions();
        if (!response.status.toString().startsWith("2")) {
          router.replace("/login");
          return;
        }
      } catch {
        router.replace("/login");
        return;
      }

      if (mounted) {
        setLoading(false);
      }
    };

    void validateSession();

    return () => {
      mounted = false;
    };
  }, [router]);

  if (loading) {
    return (
      <div className="page-container flex min-h-[40vh] items-center justify-center">
        <div className="medical-card flex items-center gap-3 text-sm text-slate-600">
          <ShieldCheck className="h-5 w-5 text-trust" />
          <span>در حال بررسی نشست کاربر...</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
