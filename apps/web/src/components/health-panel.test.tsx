import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { HealthPanel } from "./health-panel";

it("shows a database failure instead of claiming the foundation is ready", () => {
  const html = renderToStaticMarkup(<HealthPanel health={{ api: "ok", database: "unavailable", requestId: "id" }} />);
  expect(html).toContain("Bağlantı kontrolü gerekiyor");
  expect(html).toContain("Hazır değil");
  expect(html).not.toContain("Temel bağlantılar hazır");
});
