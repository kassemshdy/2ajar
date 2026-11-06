"use client";

import type { ApiErrorBody } from "@2ajar/contracts";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrf_token="))
    ?.split("=")[1];
}

type Options = { method?: string; json?: unknown; form?: FormData; retry?: boolean };

/** Browser → API (same-origin via Next rewrites). Refreshes the session once on 401. */
export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.json !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { accept: "application/json" };
  const token = csrfToken();
  if (method !== "GET" && token) headers["x-csrf-token"] = decodeURIComponent(token);
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.json !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(opts.json);
  }

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network", "network");
  }

  if (res.status === 401 && opts.retry !== false && !path.startsWith("/auth/")) {
    const refreshed = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" });
    if (refreshed.ok) return api<T>(path, { ...opts, retry: false });
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = (data as ApiErrorBody | null)?.error;
    throw new ApiError(res.status, err?.code ?? "error", err?.message ?? res.statusText, err?.details);
  }
  return data as T;
}
