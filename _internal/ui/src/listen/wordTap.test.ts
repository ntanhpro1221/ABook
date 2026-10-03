import { describe, expect, it } from "vitest";
import { offsetAtPoint, wordAtOffset, wordAtPoint } from "./wordTap";

const TEXT = "Trời vừa  hửng sáng.";

describe("wordAtOffset", () => {
  it("chạm vào chữ nào thì chữ ấy", () => {
    expect(wordAtOffset(TEXT, 0)).toBe(0);
    expect(wordAtOffset(TEXT, 3)).toBe(0);
    expect(wordAtOffset(TEXT, 5)).toBe(1);
    expect(wordAtOffset(TEXT, 10)).toBe(2);
    expect(wordAtOffset(TEXT, 18)).toBe(3); // dấu chấm dính chữ "sáng."
  });

  it("chạm vào khoảng trắng thì chữ liền sau; quá cuối thì chữ cuối", () => {
    expect(wordAtOffset(TEXT, 4)).toBe(1);
    expect(wordAtOffset(TEXT, 8)).toBe(2); // hai dấu cách
    expect(wordAtOffset(TEXT, 9)).toBe(2);
    expect(wordAtOffset(TEXT, 99)).toBe(3);
  });

  it("câu không có chữ", () => {
    expect(wordAtOffset("   ", 1)).toBe(-1);
    expect(wordAtOffset("", 0)).toBe(-1);
  });
});

/** Một "câu" giả: chữ nằm trong hai nút văn bản (như khi một chữ đang sáng tách câu thành nhiều mảnh). */
function sentence(parts: string[]) {
  const nodes = parts.map((text) => ({ text }));
  const element = {
    ownerDocument: {} as Record<string, unknown>,
    contains: (node: unknown) => nodes.includes(node as { text: string }),
  };
  const doc = element.ownerDocument;
  doc.createRange = () => {
    const range = { end: null as null | { node: { text: string }; offset: number }, setStart() {}, setEnd(node: { text: string }, offset: number) { range.end = { node, offset }; },
      toString() {
        const index = nodes.indexOf(range.end!.node);
        return parts.slice(0, index).join("") + parts[index].slice(0, range.end!.offset);
      } };
    return range;
  };
  return { element: element as unknown as HTMLElement, nodes, doc };
}

describe("offsetAtPoint / wordAtPoint", () => {
  it("dùng caretRangeFromPoint và đếm ký tự từ đầu câu, qua nhiều nút văn bản", () => {
    const { element, nodes, doc } = sentence(["Trời vừa ", "hửng", " sáng."]);
    doc.caretRangeFromPoint = () => ({ startContainer: nodes[1], startOffset: 2 });
    expect(offsetAtPoint(element, 10, 10)).toBe(11);
    expect(wordAtPoint(element, "Trời vừa hửng sáng.", 10, 10)).toBe(2);
  });

  it("dùng caretPositionFromPoint khi có (Firefox, Chrome mới)", () => {
    const { element, nodes, doc } = sentence(["Một hai"]);
    doc.caretPositionFromPoint = () => ({ offsetNode: nodes[0], offset: 5 });
    expect(wordAtPoint(element, "Một hai", 1, 1)).toBe(1);
  });

  it("chạm ngoài câu hay trình duyệt không chỉ được thì -1 (nghe từ đầu câu)", () => {
    const { element, doc } = sentence(["Một hai"]);
    expect(offsetAtPoint(element, 1, 1)).toBeNull();
    doc.caretRangeFromPoint = () => ({ startContainer: { text: "nơi khác" }, startOffset: 0 });
    expect(wordAtPoint(element, "Một hai", 1, 1)).toBe(-1);
  });
});
