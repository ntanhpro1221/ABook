import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import { Segmented } from "./ui";

// Nhóm lựa chọn xuống hàng khi khung hẹp / chữ lớn thay vì tràn ngang (soát a100 V5; đo thật 320px chữ 32px: nhóm 4 mức rộng ~445px).
beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

const options = [{ value: "0", label: "Không" }, { value: "1", label: "1 giờ" }, { value: "2", label: "2 giờ" }, { value: "3", label: "3 giờ" }];
const group = (html: string) => html.match(/<div role="radiogroup"[^>]*>/)![0];

describe("Segmented", () => {
  it("nhóm thường xuống hàng và không rộng hơn khung chứa nó", () => {
    const tag = group(renderToStaticMarkup(<Segmented label="Tự tắt" value="2" onChange={() => undefined} options={options} />));
    expect(tag).toMatch(/\binline-flex\b/);
    expect(tag).toMatch(/\bflex-wrap\b/);
    expect(tag).toMatch(/\bmax-w-full\b/);
  });

  it("nhóm `wrap` trải hết bề ngang và cũng xuống hàng", () => {
    const tag = group(renderToStaticMarkup(<Segmented wrap label="Lọc" value="2" onChange={() => undefined} options={options} />));
    expect(tag).toMatch(/\bflex\b/);
    expect(tag).toMatch(/\bflex-wrap\b/);
    expect(tag).not.toMatch(/\binline-flex\b/);
  });
});
