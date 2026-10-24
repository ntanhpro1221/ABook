import { expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { failedSourcesNote } from "./CoverSearch";
import { itemFromPath } from "@/listen/importQueue";
import { readerHint } from "@/listen/labels";
import { refusalText } from "@/studio/previewText";
import { moduleLabel, type MusicModuleStatus } from "@/studio/musicLocal";

it("lời ngắn vẫn nói được việc tiếp theo", () => {
  const picked = itemFromPath("a.jpg");
  const texts = [failedSourcesNote(["itunes"]), "error" in picked ? picked.error : "", refusalText("producing", ""), refusalText("studio", ""),
    moduleLabel({ state: "outdated", stopped: true, total: 1000 } as MusicModuleStatus)];
  for (const text of texts) expect(text.length).toBeLessThanOrEqual(85);
  expect(texts[0]).toContain("chọn ảnh"); expect(texts[1]).toContain("PDF có chữ"); expect(texts[4]).toContain("ghim tay");
});

it("nhắc màn đọc gọn, vẫn phân biệt chuột/chạm và quyền sửa", () => {
  for (const coarse of [false, true]) {
    const text = readerHint({ textOnly: false, canSpeak: false, timed: true, tapped: false, coarse, wish: true, readings: true })!;
    expect(text.length).toBeLessThanOrEqual(120); expect(text).not.toContain("\n"); expect(text).toContain(coarse ? "Chạm chữ" : "Bấm chữ");
    expect(text).toContain("đổi người nói, cách đọc hoặc thu lại");
    expect(text).toContain("Sửa câu này"); expect(text).toContain(coarse ? "Giữ chữ" : "Bấm chuột phải vào chữ");
  }
});

it("chuỗi PDF hỏng Kotlin trùng fixture mà Python/pdf.js dùng", () => {
  const fixture = JSON.parse(readFileSync(new URL("../../../tests/fixtures/import/messages.json", import.meta.url), "utf8")) as { broken: string };
  const kotlin = readFileSync(new URL("../../../mobile/android/app/src/main/java/vn/abook/player/BookImport.kt", import.meta.url), "utf8");
  expect(kotlin.match(/private const val BROKEN = "([^"]+)"/)![1].replace("%s", "PDF")).toBe(fixture.broken);
});
