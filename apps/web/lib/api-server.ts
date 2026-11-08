import "server-only";
import { cookies, headers as requestHeaders } from "next/headers";
import type { Location, Suggestion } from "@2ajar/contracts";

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export class ServerApiError extends Error {
  constructor(public status: number) {
    super(`API responded ${status}`);
  }
}

type GetOptions = {
  /** Send the visitor's cookies (private data; never cached). */
  forwardCookies?: boolean;
  /** Seconds the Next data cache may reuse a response. Only for anonymous reference data. */
  revalidate?: number;
};

/** Fetch from the API during SSR. Returns null on 404. */
export async function apiGet<T>(path: string, opts: GetOptions = {}): Promise<T | null> {
  const headers: Record<string, string> = { accept: "application/json" };
  if (opts.forwardCookies) {
    headers.cookie = (await cookies()).toString();
  }
  // Personalised or fast-changing responses are never cached; reference data (locations, config) is.
  const caching: RequestInit & { next?: { revalidate: number } } =
    opts.revalidate && !opts.forwardCookies ? { next: { revalidate: opts.revalidate } } : { cache: "no-store" };
  const res = await fetch(`${API}/api/v1${path}`, { headers, ...caching });
  if (res.status === 404) return null;
  if (!res.ok) throw new ServerApiError(res.status);
  return (await res.json()) as T;
}

/**
 * Anonymous POST from SSR on behalf of the visitor (read-only actions such as smart search). Forwards the edge's
 * X-Forwarded-For unchanged so the API rate-limits the visitor rather than this server. No cookies are sent.
 */
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const incoming = await requestHeaders();
  const headers: Record<string, string> = {
    accept: "application/json",
    "content-type": "application/json",
  };
  const forwarded = incoming.get("x-forwarded-for");
  if (forwarded) headers["x-forwarded-for"] = forwarded;
  const res = await fetch(`${API}/api/v1${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new ServerApiError(res.status);
  return (await res.json()) as T;
}

/** Reference data (locations, public config) changes only on deploy. */
export const REFERENCE_TTL = 300;

export function getLocations() {
  return apiGet<Location[]>("/locations", { revalidate: REFERENCE_TTL });
}

export interface PublicConfig {
  consent_text_version: string;
  demo_mode: boolean;
  max_upload_bytes: number;
  max_media_per_listing: number;
}

export async function getPublicConfig(): Promise<PublicConfig> {
  const cfg = await apiGet<PublicConfig>("/config", { revalidate: REFERENCE_TTL });
  if (!cfg) throw new ServerApiError(404);
  return cfg;
}

export function getSuggestions() {
  return apiGet<Suggestion[]>("/search/suggestions", { revalidate: REFERENCE_TTL });
}
