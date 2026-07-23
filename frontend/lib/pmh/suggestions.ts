export const NONE_CHIP = "هیچ‌کدام";

export const ALLERGY_SUGGESTIONS = ["پنی‌سیلین", "آسپرین", "سولفا", "لاتکس", NONE_CHIP];

export const SURGERY_SUGGESTIONS = ["آپاندکتومی", "سزارین", "کیسه صفرا", NONE_CHIP];

export const FAMILY_SUGGESTIONS = ["دیابت", "فشار خون", "بیماری قلبی", "سرطان", NONE_CHIP];

export const CHRONIC_DISEASE_SUGGESTIONS = [
  "دیابت",
  "فشار خون بالا",
  "آسم",
  "بیماری کلیوی",
  "میگرن",
  "بیماری تیروئید",
  "چربی خون",
];

const SPLIT_PATTERN = /[\n،,]+/;

export function parseChipValue(
  value: string,
  suggestions: string[],
): { selectedChips: string[]; otherText: string } {
  const trimmed = value.trim();
  if (!trimmed) {
    return { selectedChips: [], otherText: "" };
  }

  if (trimmed === NONE_CHIP) {
    return { selectedChips: [NONE_CHIP], otherText: "" };
  }

  const suggestionSet = new Set(suggestions.filter((s) => s !== NONE_CHIP));
  const tokens = trimmed
    .split(SPLIT_PATTERN)
    .map((t) => t.trim())
    .filter(Boolean);

  const selectedChips: string[] = [];
  const otherParts: string[] = [];

  for (const token of tokens) {
    if (token === NONE_CHIP) {
      return { selectedChips: [NONE_CHIP], otherText: "" };
    }
    if (suggestionSet.has(token)) {
      if (!selectedChips.includes(token)) {
        selectedChips.push(token);
      }
    } else {
      otherParts.push(token);
    }
  }

  return { selectedChips, otherText: otherParts.join("، ") };
}

export function combineChipValue(selectedChips: string[], otherText: string): string {
  if (selectedChips.length === 1 && selectedChips[0] === NONE_CHIP) {
    return NONE_CHIP;
  }

  const parts = [...selectedChips.filter((c) => c !== NONE_CHIP)];
  const trimmedOther = otherText.trim();
  if (trimmedOther) {
    parts.push(trimmedOther);
  }
  return parts.join("، ");
}
