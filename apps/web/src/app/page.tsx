import { randomUUID } from "node:crypto";
import { HealthPanel } from "../components/health-panel";
import { apiBaseUrl, readHealth } from "../lib/health";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await readHealth(apiBaseUrl(process.env.CCE_API_BASE_URL), randomUUID());
  console.info(JSON.stringify({
    event: "web_health", request_id: health.requestId,
    api: health.api, database: health.database,
  }));
  return <HealthPanel health={health} />;
}
