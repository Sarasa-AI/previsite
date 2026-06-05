import Link from "next/link";
import { ArrowLeft, CalendarDays, CheckCircle2, Clock3 } from "lucide-react";

type SessionCardProps = {
  session: {
    id: number;
    initial_complaint: string;
    created_at: string;
    status: string;
    progress: number;
  };
};

function statusMeta(status: string, progress: number) {
  if (status === "completed") {
    return {
      label: "تکمیل شده",
      progress: 100,
      chipClass: "bg-mint/50 text-trust",
      icon: CheckCircle2,
    };
  }

  if (status === "pending_review") {
    return {
      label: "در انتظار بررسی پزشک",
      progress: 100,
      chipClass: "bg-amber-100 text-amber-700",
      icon: Clock3,
    };
  }

  return {
    label: "در حال انجام",
    progress: progress || 10,
    chipClass: "bg-trust/10 text-trust",
    icon: Clock3,
  };
}

function CircularProgress({ progress }: { progress: number }) {
  const radius = 24;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (progress / 100) * circumference;

  return (
    <div className="relative h-16 w-16 shrink-0">
      <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r={radius} fill="none" stroke="rgba(148, 163, 184, 0.18)" strokeWidth="7" />
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="#1B3B5A"
          strokeLinecap="round"
          strokeWidth="7"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-all duration-500 ease-spring"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-xs font-bold text-trust">{progress}%</div>
    </div>
  );
}

export default function SessionCard({ session }: SessionCardProps) {
  const meta = statusMeta(session.status, session.progress);
  const StatusIcon = meta.icon;

  return (
    <article className="medical-card group transition-shadow duration-300 hover:shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-4">
          <div className="space-y-2">
            <span className={`status-chip ${meta.chipClass}`}>
              <StatusIcon className="h-4 w-4" />
              {meta.label}
            </span>
            <h3 className="text-xl font-bold text-slate-900">جلسه #{session.id}</h3>
            <p className="text-sm leading-7 text-slate-600">
              {session.initial_complaint || "شرح اولیه برای این جلسه ثبت نشده است."}
            </p>
          </div>

          <div className="inline-flex items-center gap-2 text-sm text-slate-500">
            <CalendarDays className="h-4 w-4" />
            {new Date(session.created_at).toLocaleDateString("fa-IR")}
          </div>
        </div>

        <CircularProgress progress={meta.progress} />
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link className="primary-button" href={`/chat/${session.id}`}>
          ادامه مصاحبه
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <Link className="secondary-button" href={`/upload/${session.id}`}>
          آپلود فایل
        </Link>
        <Link className="secondary-button" href={`/summary/${session.id}`}>
          مشاهده خلاصه
        </Link>
      </div>
    </article>
  );
}
