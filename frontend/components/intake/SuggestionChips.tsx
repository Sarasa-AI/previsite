"use client";

type SuggestionChipsProps = {
  suggestions: string[];
  onChipClick: (chip: string) => void;
  selectedChips?: string[];
  disabledChips?: string[];
  disabled?: boolean;
};

export function SuggestionChips({
  suggestions,
  onChipClick,
  selectedChips = [],
  disabledChips = [],
  disabled,
}: SuggestionChipsProps) {
  const disabledSet = new Set(disabledChips);
  const selectedSet = new Set(selectedChips);

  return (
    <div className="flex flex-wrap gap-2">
      {suggestions.map((chip) => {
        const isSelected = selectedSet.has(chip);
        const isChipDisabled = disabled || disabledSet.has(chip);

        return (
          <button
            key={chip}
            type="button"
            onClick={() => onChipClick(chip)}
            disabled={isChipDisabled}
            className={[
              "rounded-full border px-3 py-1.5 text-sm font-semibold transition-colors",
              isSelected
                ? "border-trust bg-trust/10 text-trust"
                : "border-slate-200 bg-white text-slate-700 hover:border-trust/30 hover:bg-trust/5",
              isChipDisabled ? "cursor-not-allowed opacity-50" : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {chip}
          </button>
        );
      })}
    </div>
  );
}
