import { describe, expect, it } from "vitest";
import { describePush } from "./PhoneEdits";

const push = (over: Partial<Parameters<typeof describePush>[0]>) => ({
  at: Math.floor(Date.now() / 1000),
  device: "a1b2c3d4e5f6",
  name: "Pixel",
  applied: 0,
  skipped: 0,
  requests: 0,
  waiting: 0,
  conflicts: [],
  ...over,
});

describe("kể lần điện thoại gửi phần sửa về", () => {
  it("nói máy tính đã áp, đã ghi thành yêu cầu, đang chờ duyệt và bỏ qua bao nhiêu", () => {
    const text = describePush(push({ applied: 3, requests: 1, waiting: 2, skipped: 1 }));
    expect(text).toContain("Pixel");
    expect(text).toContain("3 thay đổi đã áp, 1 việc đã thành yêu cầu, 2 việc đang chờ duyệt, 1 không còn chỗ trong sách (bỏ qua)");
  });

  it("lần gửi không mang gì mới thì nói thẳng", () => {
    expect(describePush(push({}))).toContain("không có gì mới");
  });
});

describe("lời dưới toast Áp dụng", () => {
  it("sách đang chạy: nói máy tự áp từ chương sau, không bảo bấm nút không có", async () => {
    const { applyNote } = await import("./PhoneEdits");
    const { SENTENCE } = await import("./decisions");
    const text = applyNote({ skipped: 0, held: 0 }, SENTENCE.running);
    expect(text).toContain("từ chương sau");
    expect(text).not.toContain("Áp dụng thay đổi");
  });

  it("sách đã xong: vẫn chỉ nút Áp dụng thay đổi; việc bỏ qua và việc giữ lại được kể", async () => {
    const { applyNote } = await import("./PhoneEdits");
    const { SENTENCE } = await import("./decisions");
    expect(applyNote({ skipped: 0, held: 0 }, SENTENCE.done)).toContain("Áp dụng thay đổi");
    expect(applyNote({ skipped: 2, held: 1 }, SENTENCE.done)).toBe("2 việc không còn khớp với sách nên bị bỏ qua. 1 việc máy này đã đổi khác sau đó vẫn chờ bạn chọn từng việc.");
  });

  it("kể tên các việc không áp được (tối đa ba, còn lại đếm)", async () => {
    const { applyNote } = await import("./PhoneEdits");
    const { SENTENCE } = await import("./decisions");
    expect(applyNote({ skipped: 1, held: 0, dropped: ["“A” đọc là “a”"] }, SENTENCE.done)).toBe("1 việc không còn khớp với sách nên bị bỏ qua: “A” đọc là “a”.");
    expect(applyNote({ skipped: 5, held: 0, dropped: ["một", "hai", "ba", "bốn", "năm"] }, SENTENCE.done)).toBe(
      "5 việc không còn khớp với sách nên bị bỏ qua: một; hai; ba; và 2 việc nữa.",
    );
  });
});
