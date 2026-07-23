import { cookies } from "next/headers";

import { getBackendApiUrl } from "@/lib/backend-config";

const BACKEND_API_URL = getBackendApiUrl();

export async function backendFetch(
  path: string,
  init?: RequestInit & { isFormData?: boolean },
) {
  const token = cookies().get("access_token")?.value;
  const headers = new Headers(init?.headers || {});

  if (!init?.isFormData) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(`${BACKEND_API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}
