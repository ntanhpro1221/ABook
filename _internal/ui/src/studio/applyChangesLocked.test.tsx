import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import { PendingList, type PendingItem } from "./ApplyChanges";

// Soát a83 B5: sách đang chạy thì hộp "thay đổi chờ áp" xem được nhưng nút bỏ tắt cho tới khi sách tạm dừng tới checkpoint.
const ITEM: PendingItem = { kind: "speaker", label: "“Xin chào” - Natasha", lines: 1, section: "speakers", key: "c1s2", requestedAt: 1 };

describe("danh sách thay đổi chờ áp", () => {
  it("nút bỏ bật khi sách không chạy hay đã tạm dừng tới checkpoint", () => {
    const html = renderToString(<TooltipProvider><PendingList items={[ITEM]} dropping={null} onDrop={() => undefined} /></TooltipProvider>);
    expect(html).toContain("Bỏ đổi người nói");
    expect(html).not.toContain('disabled=""');
  });

  it("nút bỏ tắt khi sách đang chạy", () => {
    const html = renderToString(<TooltipProvider><PendingList items={[ITEM]} dropping={null} onDrop={() => undefined} locked /></TooltipProvider>);
    expect(html).toContain('disabled=""');
  });
});
