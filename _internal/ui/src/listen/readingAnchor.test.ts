import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { anchorOf, makeAnchor, restoreAnchor, textFingerprint } from "./readingAnchor";

it("anchorOf nuốt lỗi của máy phát: lưu tiến độ không mất vì mốc chữ - soát a79 lỗi 4", () => {
  const broken = { get readingAnchor(): never { throw new TypeError("hỏng"); } };
  expect(anchorOf(broken)).toBeUndefined();
  expect(anchorOf({ readingAnchor: { segment: 1, charOffset: 2, textHash: "h" } })).toEqual({ segment: 1, charOffset: 2, textHash: "h" });
  expect(anchorOf({})).toBeUndefined();
});

it("cùng vân tay và offset Unicode với ReadingAnchorTest trên JVM", () => {
  const paragraphs = ["Chương một", "😀 Một hai ba.", "Đoạn sau."];
  expect(textFingerprint(paragraphs)).toBe("fnv1a64:bb657205cfbee8a0");
  const anchor = makeAnchor(paragraphs, 1, 2)!;
  expect(anchor.charOffset).toBe(6);
  expect(restoreAnchor(paragraphs, anchor)).toEqual({ segment: 1, word: 2 });
  expect(restoreAnchor(["Chương một", "😀 Một hai bốn.", "Đoạn sau."], anchor)).toBeUndefined(); // chính đoạn đang nghe đã đổi
  expect(restoreAnchor([...paragraphs, "Mới"], anchor)).toEqual({ segment: 1, word: 2 }); // đổi ở đoạn khác thì giữ chỗ (soát a79 lỗi 5)
  expect(restoreAnchor(paragraphs, { ...anchor, segment: 99 })).toBeUndefined();
  expect(restoreAnchor(paragraphs, { ...anchor, charOffset: 1.5 })).toBeUndefined();
});

interface Fixture {
  anchor: { paragraphs: string[]; segment: number; word: number; expect: ReturnType<typeof makeAnchor> };
  cases: { name: string; before: string[]; segment: number; word: number; after: string[]; expect: { segment: number; word: number } | null }[];
}
const fixture = JSON.parse(readFileSync(new URL("../../../tests/fixtures/reading_anchor/restore.json", import.meta.url), "utf8")) as Fixture;

it("mốc dựng ra khớp từng byte với bộ ví dụ dùng chung (ReadingAnchorTest.kt cùng đọc file này)", () => {
  expect(makeAnchor(fixture.anchor.paragraphs, fixture.anchor.segment, fixture.anchor.word)).toEqual(fixture.anchor.expect);
});

for (const item of fixture.cases) {
  it(`khôi phục sau khi sách đổi - ${item.name}`, () => {
    const anchor = makeAnchor(item.before, item.segment, item.word)!;
    expect(restoreAnchor(item.after, anchor) ?? null).toEqual(item.expect);
  });
}

it("mốc cũ chưa có băm đoạn: băm chương lệch thì bỏ như trước", () => {
  const { paragraphHash: _skip, ...old } = makeAnchor(["một", "hai ba"], 1, 1)!;
  expect(restoreAnchor(["một", "hai ba"], old)).toEqual({ segment: 1, word: 1 });
  expect(restoreAnchor(["một", "hai ba", "bốn"], old)).toBeUndefined();
});
