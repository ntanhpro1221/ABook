import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { expect, it } from "vitest";
import { ShortName } from "./ShortName";

// Full-source CSS/JSX policy lives in scripts/text_cut_scan.test.mjs; no mini
// player or device-name exemptions remain. This guards programmatic shortening.
it("shows the complete device name in the shared label", () => {
  const name = "Máy tính của bạn — Nguyễn Hoàng Anh — Phòng đọc sách tầng ba";
  const html = renderToStaticMarkup(createElement(ShortName, { name }));
  expect(html).toContain(name);
  expect(html).not.toContain("…");
  expect(html).not.toMatch(/hidden|title=/);
});
