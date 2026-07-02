"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";

type PMHCategoryCardProps = {
  title: string;
  prompt: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
};

export function PMHCategoryCard({ title, prompt, defaultOpen = false, children }: PMHCategoryCardProps) {
  const [open, setOpen] = React.useState(defaultOpen);

  return (
    <section className="medical-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start justify-between gap-3 text-right"
        aria-expanded={open}
      >
        <span className="min-w-0">
          <span className="block text-sm font-bold text-trust">{title}</span>
          <span className="mt-1 block text-sm leading-7 text-slate-700">{prompt}</span>
        </span>
        <ChevronDown
          className={`mt-1 h-5 w-5 shrink-0 text-slate-500 transition-transform duration-300 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity] duration-300 ease-out ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="mt-4 space-y-3">{children}</div>
        </div>
      </div>
    </section>
  );
}

