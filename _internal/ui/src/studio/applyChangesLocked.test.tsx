import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/shared/ui";
import { PendingList, type PendingItem } from "./ApplyChanges";

// Soát a89 T2: bỏ một thay đổi chờ áp không còn phải đợi sách tạm dừng - máy chủ rút được lúc sách chạy và từ chối việc đã áp, nên nút bỏ luôn bật (trừ lúc đang bỏ dở).
const ITEM: PendingItem = { kind: "speaker", label: "“Xin chào” - Natasha", lines: 1, section: "speakers", key: "c1s2", requestedAt: 1 };

describe("danh sách thay đổi chờ áp", () => {
  it("nút bỏ bật, sách chạy hay không", () => {
    const html = renderToString(<TooltipProvider><PendingList items={[ITEM]} dropping={null} onDrop={() => undefined} /></TooltipProvider>);
    expect(html).toContain("Bỏ đổi người nói");
    expect(html).not.toContain('disabled=""');
  });

  it("đang bỏ dở một việc thì nút bỏ tắt để khỏi bấm hai lần", () => {
    const html = renderToString(<TooltipProvider><PendingList items={[ITEM]} dropping="speakers:c1s2" onDrop={() => undefined} /></TooltipProvider>);
    expect(html).toContain('disabled=""');
  });
});
