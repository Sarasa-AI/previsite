/** Iranian national ID validation (10 digits + standard checksum). */
export function validateIranianNationalId(nationalId: string): boolean {
  if (!/^\d{10}$/.test(nationalId)) return false;
  if (new Set(nationalId).size === 1) return false;

  const checkDigit = Number(nationalId[9]);
  const weightedSum =
    nationalId
      .slice(0, 9)
      .split("")
      .reduce((sum, digit, index) => sum + Number(digit) * (10 - index), 0) % 11;

  if (weightedSum < 2) return checkDigit === weightedSum;
  return checkDigit === 11 - weightedSum;
}

export const AUTH_ERROR_MESSAGES: Record<string, string> = {
  USER_EXISTS: "این کاربر قبلاً ثبت‌نام کرده است",
  INVALID_NATIONAL_ID: "کد ملی وارد شده معتبر نیست",
};

export function mapAuthError(detail: string | undefined, fallback: string): string {
  if (!detail) return fallback;
  return AUTH_ERROR_MESSAGES[detail] ?? detail;
}
