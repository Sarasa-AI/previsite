/** Persian / Arabic-Indic digit normalization for phone and OTP inputs. */

const DIGIT_MAP: Record<string, string> = {
  "۰": "0",
  "۱": "1",
  "۲": "2",
  "۳": "3",
  "۴": "4",
  "۵": "5",
  "۶": "6",
  "۷": "7",
  "۸": "8",
  "۹": "9",
  "٠": "0",
  "١": "1",
  "٢": "2",
  "٣": "3",
  "٤": "4",
  "٥": "5",
  "٦": "6",
  "٧": "7",
  "٨": "8",
  "٩": "9",
};

export function toAsciiDigits(value: string): string {
  return Array.from(value || "")
    .map((ch) => DIGIT_MAP[ch] ?? ch)
    .join("");
}

/** Best-effort client normalize toward E.164 +98… (server is authoritative). */
export function normalizeIranianMobileClient(raw: string): string {
  let text = toAsciiDigits(raw).replace(/[\s\-_.]+/g, "");
  if (text.startsWith("0098")) text = "+98" + text.slice(4);
  else if (text.startsWith("98") && !text.startsWith("+")) text = "+" + text;
  else if (text.startsWith("09")) text = "+98" + text.slice(1);
  else if (/^9\d{9}$/.test(text)) text = "+98" + text;
  return text;
}
