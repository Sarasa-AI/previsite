const DEV_BACKEND_URL = "http://localhost:8000";

/**
 * Centralized backend URL resolver.
 * Server-side code uses BACKEND_API_URL first, then NEXT_PUBLIC_API_URL, then fallback to localhost:8000 in dev.
 */
export function getBackendApiUrl(): string {
  let url = process.env.BACKEND_API_URL?.trim();
  
  if (!url) {
    url = process.env.NEXT_PUBLIC_API_URL?.trim();
  }

  if (!url) {
    if (process.env.NODE_ENV === "production") {
      throw new Error(
        "BACKEND_API_URL or NEXT_PUBLIC_API_URL is required in production. Set it in Liara env vars for the sarasa-ai app.",
      );
    }
    url = DEV_BACKEND_URL;
  }

  return url.replace(/\/$/, "");
}
