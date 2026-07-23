/** Client-side Sentry bootstrap — no-op when NEXT_PUBLIC_SENTRY_DSN is unset. */

let initialized = false;

export function initClientSentry(): void {
  if (initialized || typeof window === "undefined") return;
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN?.trim();
  if (!dsn) return;

  void import("@sentry/nextjs")
    .then((Sentry) => {
      Sentry.init({
        dsn,
        environment: process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV,
        tracesSampleRate: 0,
        sendDefaultPii: false,
      });
      initialized = true;
    })
    .catch(() => {
      // Package missing or init failed — stay silent so the app never crashes.
    });
}
