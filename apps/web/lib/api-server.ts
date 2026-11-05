import "server-only";
import { cookies } from "next/headers";

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export class ServerApiError extends Error {
  constructor(public status: number) {
    super(`API responded ${status}`);
  }
}

/** Fetch from the API during SSR. Returns null on 404. */
export async function apiGet<T>(path: string, opts: { forwardCookies?: boolean } = {}): Promise<T | null> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (opts.forwardCookies) {
    headers.cookie = (await cookies()).toString();
  }
  const res = await fetch(`${API}/api/v1${path}`, { headers, cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new ServerApiError(res.status);
  return (await res.json()) as T;
}

export interface PublicConfig {
  consent_text_version: string;
  demo_mode: boolean;
  max_upload_bytes: number;
  max_media_per_listing: number;
}

export async function getPublicConfig(): Promise<PublicConfig> {
  const cfg = await apiGet<PublicConfig>("/config");
  if (!cfg) throw new ServerApiError(404);
  return cfg;
}
