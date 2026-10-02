/** Map structured OTP / auth error codes to Persian UI messages. */

const OTP_ERROR_MAP: Record<string, string> = {
  INVALID_PHONE: "شماره موبایل معتبر نیست",
  INVALID_OTP: "کد وارد شده صحیح نیست",
  OTP_EXPIRED: "کد منقضی شده است؛ دوباره درخواست دهید",
  OTP_LOCKED: "تعداد تلاش‌ها بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید",
  OTP_COOLDOWN: "لطفاً قبل از درخواست مجدد کمی صبر کنید",
  OTP_RATE_LIMITED: "تعداد درخواست‌ها بیش از حد مجاز است؛ بعداً تلاش کنید",
  OTP_DISABLED: "ورود با پیامک در حال حاضر غیرفعال است",
  INVALID_LINK_TOKEN: "نشست پیوند شماره منقضی شده است؛ دوباره وارد شوید",
  PHONE_IN_USE: "این شماره قبلاً ثبت شده است",
  LEGACY_LOGIN_DISABLED: "ورود با کد ملی دیگر پشتیبانی نمی‌شود",
  REGISTER_DISABLED: "ثبت‌نام با رمز عبور غیرفعال است؛ از شماره موبایل استفاده کنید",
  ACCOUNT_INACTIVE: "حساب کاربری غیرفعال است",
  PHONE_LINK_REQUIRED: "برای ادامه، شماره موبایل خود را تأیید کنید",
};

export function mapOtpError(detail: string | undefined, fallback: string): string {
  if (!detail) return fallback;
  return OTP_ERROR_MAP[detail] ?? fallback;
}

export { OTP_ERROR_MAP };
