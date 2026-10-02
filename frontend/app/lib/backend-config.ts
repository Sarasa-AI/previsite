const PROD_BACKEND_URL = "https://api.treat-ai.ir";

export function getBackendApiUrl(): string {
  let url = process.env.BACKEND_API_URL?.trim();

  if (!url) {
    url = process.env.NEXT_PUBLIC_API_URL?.trim();
  }

  if (!url) {
    if (process.env.NODE_ENV === "production") {
      return PROD_BACKEND_URL;
    }
    url = "http://localhost:8000";
  }

  return url.replace(/\/$/, "");
}
