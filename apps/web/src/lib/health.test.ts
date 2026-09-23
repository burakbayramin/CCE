import { describe, expect, it, vi } from "vitest";
import { apiBaseUrl, readHealth } from "./health";

describe("health boundary", () => {
  it("keeps API liveness when database readiness fails and propagates correlation", async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation(async (url) =>
      String(url).endsWith("/live")
        ? Response.json({ status: "ok" })
        : Response.json({ status: "unavailable" }, { status: 503 }),
    );
    const health = await readHealth("http://localhost:8000", "test-request", fetcher);
    expect(health.api).toBe("ok");
    expect(health.database).toBe("unavailable");
    expect(fetcher.mock.calls[0][1]?.headers).toEqual({ "X-Request-ID": "test-request" });
    expect(fetcher.mock.calls[0][1]?.cache).toBe("no-store");
  });

  it("does not report malformed or failed HTTP responses as healthy", async () => {
    for (const response of [Response.json({ status: "ok" }, { status: 500 }), Response.json({})]) {
      const fetcher = vi.fn<typeof fetch>().mockImplementation(async () => response.clone());
      expect((await readHealth("http://localhost:8000", "id", fetcher)).database).toBe("unreachable");
    }
  });

  it("handles offline API without exposing exception details", async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new Error("private-error"));
    const health = await readHealth("http://localhost:8000", "id", fetcher);
    expect(health).toEqual({ api: "unreachable", database: "unreachable", requestId: "id" });
    expect(JSON.stringify(health)).not.toContain("private-error");
  });

  it("rejects credentials and invalid server URLs", () => {
    expect(() => apiBaseUrl("http://secret:password@host")).toThrow();
    expect(() => apiBaseUrl("file:///etc/passwd")).toThrow();
    expect(apiBaseUrl(undefined)).toBe("http://127.0.0.1:8000");
  });
});
