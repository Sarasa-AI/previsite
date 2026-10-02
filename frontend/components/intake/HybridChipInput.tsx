"use client";

import { useEffect, useState } from "react";
import { SuggestionChips } from "@/components/intake/SuggestionChips";
import { combineChipValue, NONE_CHIP, parseChipValue } from "@/lib/pmh/suggestions";

type HybridChipInputProps = {
  label: string;
  value: string;
  suggestions: string[];
  onChange: (value: string) => void;
  otherPlaceholder?: string;
  disabled?: boolean;
};

export function HybridChipInput({
  label,
  value,
  suggestions,
  onChange,
  otherPlaceholder = "موارد دیگر را بنویسید...",
  disabled,
}: HybridChipInputProps) {
  const [selectedChips, setSelectedChips] = useState<string[]>([]);
  const [otherText, setOtherText] = useState("");

  useEffect(() => {
    const parsed = parseChipValue(value, suggestions);
    setSelectedChips(parsed.selectedChips);
    setOtherText(parsed.otherText);
  }, [value, suggestions]);

  const emitChange = (chips: string[], other: string) => {
    onChange(combineChipValue(chips, other));
  };

  const handleChipClick = (chip: string) => {
    if (disabled) {
      return;
    }

    if (chip === NONE_CHIP) {
      setSelectedChips([NONE_CHIP]);
      setOtherText("");
      emitChange([NONE_CHIP], "");
      return;
    }

    setSelectedChips((prev) => {
      const withoutNone = prev.filter((c) => c !== NONE_CHIP);
      const next = withoutNone.includes(chip)
        ? withoutNone.filter((c) => c !== chip)
        : [...withoutNone, chip];
      emitChange(next, otherText);
      return next;
    });
  };

  const handleOtherChange = (nextOther: string) => {
    setOtherText(nextOther);
    const chipsWithoutNone = selectedChips.filter((c) => c !== NONE_CHIP);
    if (nextOther.trim() && selectedChips.includes(NONE_CHIP)) {
      setSelectedChips([]);
      emitChange([], nextOther);
      return;
    }
    emitChange(chipsWithoutNone, nextOther);
  };

  const noneSelected = selectedChips.includes(NONE_CHIP);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <SuggestionChips
        suggestions={suggestions}
        selectedChips={selectedChips}
        onChipClick={handleChipClick}
        disabled={disabled}
      />
      <div className="space-y-1">
        <label className="block text-xs font-medium text-slate-500">سایر موارد</label>
        <input
          type="text"
          className="field-input"
          value={otherText}
          onChange={(e) => handleOtherChange(e.target.value)}
          placeholder={otherPlaceholder}
          disabled={disabled || noneSelected}
        />
      </div>
    </div>
  );
}
