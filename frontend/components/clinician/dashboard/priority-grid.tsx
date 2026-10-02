import type { ReactNode } from "react";
import { AcuityCard, type AcuityTier } from "@/components/clinician/dashboard/acuity-card";
import { BidiText } from "@/components/shared/bidi-text";
import { cn } from "@/lib/utils";

export type PriorityPatient = {
  id: string;
  tier: AcuityTier;
  title: string;
  subtitle?: ReactNode;
  detail?: ReactNode;
};

const RANK: Record<Exclude<AcuityTier, "unknown">, number> = { P0: 0, P1: 1, P2: 2, P3: 3 };

const MOCK_PATIENTS: PriorityPatient[] = [
  { id: "pv-104", tier: "P2", title: "مریم احمدی", subtitle: <><BidiText>۶۸</BidiText> سال · <BidiText>09:40</BidiText></>, detail: "در انتظار بررسی پرونده" },
  { id: "pv-101", tier: "P0", title: "رضا کریمی", subtitle: <><BidiText>۵۴</BidiText> سال · <BidiText>09:15</BidiText></>, detail: "نیازمند بررسی فوری صف" },
  { id: "pv-105", tier: "unknown", title: "الهام موسوی", subtitle: <><BidiText>۴۱</BidiText> سال · <BidiText>10:05</BidiText></>, detail: "سطح فوریت تعیین نشده" },
  { id: "pv-102", tier: "P3", title: "سارا نادری", subtitle: <><BidiText>۳۲</BidiText> سال · <BidiText>09:30</BidiText></>, detail: "در انتظار بررسی پرونده" },
  { id: "pv-103", tier: "P1", title: "حسین رضایی", subtitle: <><BidiText>۷۲</BidiText> سال · <BidiText>09:25</BidiText></>, detail: "در صف بررسی" },
];

function sortRankedPatients(patients: PriorityPatient[]) {
  return patients
    .filter((patient) => patient.tier !== "unknown")
    .sort((a, b) => RANK[a.tier as Exclude<AcuityTier, "unknown">] - RANK[b.tier as Exclude<AcuityTier, "unknown">]);
}

export type PriorityGridProps = {
  patients?: PriorityPatient[];
  className?: string;
};

export function PriorityGrid({ patients = MOCK_PATIENTS, className }: PriorityGridProps) {
  const rankedPatients = sortRankedPatients(patients);
  const unknownPatients = patients.filter((patient) => patient.tier === "unknown");

  return (
    <section aria-labelledby="priority-grid-title" className={cn("space-y-5", className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[hsl(var(--pv-navy-900))]">صف اولویت</p>
          <h2 id="priority-grid-title" className="mt-1 text-2xl font-bold text-[hsl(var(--pv-ink-950))]">بیماران در انتظار بررسی</h2>
        </div>
        <p className="text-sm text-[hsl(var(--pv-ink-950)/.7)]">مرتب‌سازی بر اساس سطح اولویت</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="بیماران مرتب‌شده بر اساس اولویت">
        {rankedPatients.map((patient) => (
          <AcuityCard key={patient.id} tier={patient.tier} title={patient.title} subtitle={patient.subtitle}>
            {patient.detail}
          </AcuityCard>
        ))}
      </div>

      {unknownPatients.length > 0 ? (
        <section aria-labelledby="unknown-priority-title" className="space-y-3 border-t-2 border-[hsl(var(--acuity-unknown))] pt-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 id="unknown-priority-title" className="text-lg font-bold text-[hsl(var(--acuity-unknown))]">سطح فوریت تعیین نشده</h3>
            <p className="text-sm text-[hsl(var(--pv-ink-950)/.7)]">این موارد در رتبه‌بندی اولویت قرار نگرفته‌اند.</p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {unknownPatients.map((patient) => (
              <AcuityCard key={patient.id} tier={patient.tier} title={patient.title} subtitle={patient.subtitle}>
                {patient.detail}
              </AcuityCard>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}

export { MOCK_PATIENTS };
