import { describe, expect, it, vi } from "vitest";
import { json, mockFetch } from "@/test/utils";
import { api, ApiError } from "./api-client";

describe("api client", () => {
  it("sends JSON with the CSRF header on mutations only", async () => {
    document.cookie = "csrf_token=tok%3D1; path=/";
    const calls = mockFetch({ "POST /api/v1/x": { ok: 1 }, "GET /api/v1/y": { ok: 2 } });
    expect(await api("/x", { json: { a: 1 } })).toEqual({ ok: 1 });
    expect(await api("/y")).toEqual({ ok: 2 });
    const post = calls[0].init.headers as Record<string, string>;
    expect(post["x-csrf-token"]).toBe("tok=1");
    expect(post["content-type"]).toBe("application/json");
    expect(calls[0].init.body).toBe('{"a":1}');
    expect((calls[1].init.headers as Record<string, string>)["x-csrf-token"]).toBeUndefined();
  });

  it("posts FormData without a JSON content type", async () => {
    const calls = mockFetch({ "POST /api/v1/upload": { id: "m" } });
    const form = new FormData();
    await api("/upload", { form });
    expect(calls[0].init.body).toBe(form);
    expect((calls[0].init.headers as Record<string, string>)["content-type"]).toBeUndefined();
  });

  it("refreshes the session once on 401 and retries", async () => {
    let n = 0;
    const calls = mockFetch({
      "GET /api/v1/me": () => (n++ === 0 ? json({}, 401) : json({ id: "u" })),
      "POST /api/v1/auth/refresh": { id: "u" },
    });
    expect(await api("/me")).toEqual({ id: "u" });
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      "GET /api/v1/me",
      "POST /api/v1/auth/refresh",
      "GET /api/v1/me",
    ]);
  });

  it("throws the API error envelope when refresh fails", async () => {
    mockFetch({
      "GET /api/v1/me": () => json({ error: { code: "unauthorized", message: "Authentication required" } }, 401),
      "POST /api/v1/auth/refresh": 401,
    });
    await expect(api("/me")).rejects.toMatchObject({ status: 401, code: "unauthorized" });
  });

  it("does not try to refresh for auth endpoints and handles bodies that are not JSON", async () => {
    const calls = mockFetch({ "POST /api/v1/auth/login": () => new Response("oops", { status: 500, statusText: "Boom" }) });
    const err = (await api("/auth/login", { json: {} }).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("Boom");
    expect(err.code).toBe("error");
    expect(calls).toHaveLength(1);
  });

  it("returns undefined for 204 and maps network failures", async () => {
    mockFetch({ "DELETE /api/v1/m": 204 });
    expect(await api("/m", { method: "DELETE" })).toBeUndefined();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(api("/m")).rejects.toMatchObject({ status: 0, code: "network" });
  });
});
