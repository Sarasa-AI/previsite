"use client";

import * as React from "react";
import type { PMHFollowup } from "@/lib/pmh/types";

type PMHFollowupsProps = {
  followups: PMHFollowup[];
  values: Record<string, string>;
  onChange: (followupId: string, value: string) => void;
};

function FollowupField({
  followup,
  value,
  onChange,
}: {
  followup: PMHFollowup;
  value: string;
  onChange: (value: string) => void;
}) {
  // Current schema observations: mostly text_input; keep renderer extensible.
  const ui = followup.ui_type;

  if (ui === "date") {
    return (
      <label className="block space-y-1">
        <span className="block text-xs font-semibold text-slate-600">{followup.patient_text}</span>
        <input
          type="date"
          className="field-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </label>
    );
  }

  return (
    <label className="block space-y-1">
      <span className="block text-xs font-semibold text-slate-600">{followup.patient_text}</span>
      <input
        type="text"
        inputMode="text"
        className="field-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="مثلاً ۱۳۹۸"
      />
    </label>
  );
}

export function PMHFollowups({ followups, values, onChange }: PMHFollowupsProps) {
  if (!followups.length) return null;

  return (
    <div className="mt-2 space-y-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3">
      {followups.map((f) => (
        <FollowupField
          key={f.id}
          followup={f}
          value={values[f.id] ?? ""}
          onChange={(v) => onChange(f.id, v)}
        />
      ))}
    </div>
  );
}

