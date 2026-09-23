import type { components } from "./api/generated/schema";

type Health = components["schemas"]["Health"];
export type HealthState = "ok" | "unavailable" | "unreachable";
export type HealthSnapshot = {
  api: HealthState;
  database: HealthState;
  requestId: string;
};

export function apiBaseUrl(value: string | undefined): string {
  const url = new URL(value ?? "http://127.0.0.1:8000");
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
      || url.search || url.hash || url.pathname !== '/') {
    throw new Error("CCE_API_BASE_URL must be an HTTP(S) origin without credentials");
  }
  return url.origin;
}

export async function readHealth(
  baseUrl: string,
  requestId: string,
  fetcher: typeof fetch = fetch,
): Promise<HealthSnapshot> {
  async function probe(path: string): Promise<HealthState> {
    try {
      const response = await fetcher(`${baseUrl}${path}`, {
        cache: "no-store",
        headers: { "X-Request-ID": requestId },
        signal: AbortSignal.timeout(6000),
      });
      const body: unknown = await response.json();
      if (typeof body !== "object" || body === null || !("status" in body)) {
        return "unreachable";
      }
      const status: Health["status"] | undefined =
        body.status === "ok" || body.status === "unavailable" ? body.status : undefined;
      if (response.status === 200 && status === "ok") return "ok";
      if (response.status === 503 && status === "unavailable") return "unavailable";
      return "unreachable";
    } catch {
      return "unreachable";
    }
  }
  const [api, database] = await Promise.all([probe("/health/live"), probe("/health/ready")]);
  return { api, database, requestId };
}
