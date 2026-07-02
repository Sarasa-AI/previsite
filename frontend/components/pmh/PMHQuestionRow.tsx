"use client";

import * as React from "react";

type PMHQuestionRowProps = {
  id: string;
  text: string;
  checked: boolean;
  onChange: (next: boolean) => void;
};

export function PMHQuestionRow({ id, text, checked, onChange }: PMHQuestionRowProps) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-start justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-trust/40"
    >
      <span className="min-w-0 text-sm leading-7 text-slate-800">{text}</span>
      <span className="flex items-center">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="h-5 w-5 accent-trust"
        />
      </span>
    </label>
  );
}

