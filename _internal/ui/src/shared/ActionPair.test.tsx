import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { ActionPair, Button } from "./ui";

it("keeps a primary and a secondary together while preserving their actions and states", () => {
  const markup = renderToStaticMarkup(<ActionPair
    primary={<Button aria-pressed>Nghe thử</Button>}
    secondary={<Button variant="primary" disabled>Tải về</Button>}
  />);
  expect(markup).toContain("data-action-pair");
  expect(markup.match(/data-variant="primary"/g)).toHaveLength(1);
  expect(markup.match(/data-variant="outline"/g)).toHaveLength(1);
  expect(markup).toContain('aria-pressed="true"');
  expect(markup).toContain('disabled=""');
});
