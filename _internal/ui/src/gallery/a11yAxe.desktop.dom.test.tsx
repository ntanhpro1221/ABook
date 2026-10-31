// @vitest-environment jsdom
import axe from "axe-core";
import { expect, it } from "vitest";
import { ENTRIES } from "./entries";
import { attachHidingCss, installJsdomGallery } from "./jsdomShim";
import { galleryState } from "./state";

// Trợ năng máy tính: axe-core quét MỌI cảnh phòng trưng bày phía máy tính (cây desktop/App.tsx thật trên dữ liệu giả) - mọi luật WCAG 2.x A / AA
// và "thực hành tốt" của axe. Không có vi phạm nào được giữ lại.
// - Tương phản màu: jsdom không tính được màu thật (không bố cục, không CSS của app) - `npm run contrast` đo mọi cặp token, kể cả vòng tiêu điểm 3:1.
// - "region" (mọi nội dung nằm trong một mốc trang): menu / bảng nổi / thông báo của Radix và sonner gắn ở cuối <body>, ngoài <main> - đó là
//   cách của mọi lớp nổi; luật này chỉ quét phần còn lại của trang.

installJsdomGallery("desktop");

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa", "best-practice"];
const LAYERS = [["[data-radix-popper-content-wrapper]"], ["[data-sonner-toaster]"], ['[role="dialog"]'], ['[role="alertdialog"]']];

type Found = { rule: string; target: string; html: string; why: string };

async function violations(): Promise<Found[]> {
  const page = await axe.run(document, { runOnly: { type: "tag", values: TAGS }, rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
  const regions = await axe.run({ include: [["html"]], exclude: LAYERS } as axe.ElementContext, { runOnly: { type: "rule", values: ["region"] } });
  return [...page.violations, ...regions.violations].flatMap((rule) =>
    rule.nodes.map((node) => ({ rule: rule.id, target: node.target.join(" "), html: node.html.slice(0, 200), why: node.failureSummary ?? "" })),
  );
}

const entries = ENTRIES.filter((entry) => entry.platform === "desktop");

it("quét đủ cảnh máy tính", () => expect(entries.length).toBeGreaterThan(60));

for (const entry of entries) {
  it(`axe: ${entry.id} - ${entry.title}`, async () => {
    const { runEntry } = await import("./run");
    attachHidingCss();
    const container = document.createElement("div");
    document.body.append(container);
    const unmount = await runEntry(entry, "light", container, { quiet: 120 });
    try {
      // Cảnh phải tới đúng trạng thái (thao tác chạy hết) thì kết quả quét mới có nghĩa.
      expect(galleryState.errors, galleryState.errors.join("\n")).toEqual([]);
      expect(await violations()).toEqual([]);
      // Thanh tua đọc đúng chữ trên thanh: "12:30 / 45:00".
      for (const seek of document.querySelectorAll('[role="slider"][aria-label="Vị trí trong chương"]')) {
        expect(seek.getAttribute("aria-valuetext")).toMatch(/^(\d+:)?\d+:\d\d \/ (\d+:)?\d+:\d\d$/);
      }
    } finally {
      unmount();
      container.remove();
      document.body.replaceChildren();
    }
  }, 60_000);
}
