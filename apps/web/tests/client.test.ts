import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError, api } from "../src/api/client";

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns JSON on 2xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ x: 1 }), { status: 200 })));
    await expect(api<{ x: number }>("/api/x")).resolves.toEqual({ x: 1 });
  });

  it("throws ApiError with status on non-2xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), { status: 401 })
    ));
    await expect(api("/api/x")).rejects.toBeInstanceOf(ApiError);
  });
});
