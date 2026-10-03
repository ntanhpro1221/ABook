import { describe, expect, it } from "vitest";
import { bookProgressText, nextChapterLabel, otherBookLine, PREPARING_VOICE, primaryListenLabel, readerHint, resumeWhere, tapVerb, textBookLine, textChapterLine, toggleLabel } from "./labels";

const fresh = { playingHere: false, finished: false, point: { title: "Chương 1", at: 0 }, heard: 0, textOnly: false };

describe("nút chính của trang sách", () => {
  it("sách mới: 'Nghe ngay' cho sách chỉ có chữ, 'Bắt đầu nghe' cho sách nói", () => {
    expect(primaryListenLabel({ ...fresh, textOnly: true })).toBe("Nghe ngay");
    expect(primaryListenLabel(fresh)).toBe("Bắt đầu nghe");
  });

  it("có tiến độ: nói nghe tiếp từ đâu, cùng dạng với thẻ ở Thư viện", () => {
    const label = primaryListenLabel({ ...fresh, textOnly: true, point: { title: "Chương 3", at: 724 }, heard: 900 });
    expect(label).toBe(`Nghe tiếp · ${resumeWhere("Chương 3", 724)}`);
    expect(resumeWhere("Chương 3", 724)).toBe("Chương 3 · 12:04");
    expect(primaryListenLabel({ ...fresh, point: { title: "Chương 2", at: 0 }, heard: 300 })).toBe("Nghe tiếp · Chương 2");
  });

  it("đang phát: Tạm dừng; nghe hết sách: Nghe lại từ đầu", () => {
    expect(primaryListenLabel({ ...fresh, playingHere: true, heard: 10 })).toBe("Tạm dừng");
    expect(primaryListenLabel({ ...fresh, finished: true, heard: 9999 })).toBe("Nghe lại từ đầu");
  });
});

describe("dòng tiến độ ở màn Đang nghe", () => {
  const base = { whole: false, heard: 330, total: 3300, rate: 1, speed: "1×" };

  it("tốc độ thường: đã nghe bao nhiêu, còn bao lâu", () => {
    expect(bookProgressText(base)).toBe("Đã nghe 10% phần đã có · còn 50 phút");
    expect(bookProgressText({ ...base, whole: true })).toContain("Đã nghe 10% cả cuốn");
  });

  it("tốc độ khác: chỉ nói thời gian còn lại ở tốc độ đang chọn, không hai con số lẫn nhau", () => {
    const text = bookProgressText({ ...base, rate: 1.5, speed: "1,5×" });
    expect(text).toBe("Đã nghe 10% phần đã có · còn khoảng 33 phút ở tốc độ 1,5×");
  });
});

describe("nút phát", () => {
  it("đang chờ giọng đọc: không nói 'Tạm dừng'", () => {
    expect(toggleLabel(true, true, true)).toBe(PREPARING_VOICE);
    expect(toggleLabel(true, true, false)).toBe("Đang tải âm thanh…");
    expect(toggleLabel(true, false, true)).toBe("Tạm dừng");
    expect(toggleLabel(false, true, true)).toBe("Phát");
  });

  it("chương cuối nói là chương cuối", () => {
    expect(nextChapterLabel(false, false)).toBe("Đây là chương cuối");
    expect(nextChapterLabel(false, true)).toBe("Chương sau chưa có audio");
    expect(nextChapterLabel(true, true)).toBe("Chương sau (Shift+→)");
  });
});

describe("sách chỉ có chữ", () => {
  it("một dòng nhất quán, không 'chưa có âm thanh' cạnh nút Nghe ngay", () => {
    expect(textBookLine(true)).toBe("Chỉ có chữ · nghe bằng giọng đọc");
    expect(textBookLine(false)).toBe("Chỉ có chữ · máy này chưa có giọng đọc");
    expect(textChapterLine(true)).toBe("Giọng máy đọc");
    expect(textChapterLine(false)).toBe("Chỉ có chữ");
  });
});

describe("lời nhắc màn đọc", () => {
  const base = { textOnly: true, canSpeak: true, timed: false, tapped: false, coarse: false, wish: false };

  it("bấm với chuột, chạm với màn cảm ứng", () => {
    expect(tapVerb(false)).toBe("Bấm");
    expect(tapVerb(true)).toBe("Chạm");
    expect(readerHint(base)).toContain("Bấm vào một chữ");
    expect(readerHint({ ...base, coarse: true })).toContain("Chạm vào một chữ");
  });

  it("không đổi khi giọng máy đã đọc xong đoạn đầu (kịch bản có mốc)", () => {
    expect(readerHint({ ...base, timed: true })).toBe(readerHint(base));
    expect(readerHint({ ...base, tapped: true })).toBe("Chỉ có chữ · nghe bằng giọng đọc.");
  });

  it("sách nói của Studio", () => {
    const audio = { ...base, textOnly: false, canSpeak: false, timed: true };
    expect(readerHint(audio)).toBe("Bấm vào một chữ để nghe từ đúng chữ ấy.");
    expect(readerHint({ ...audio, tapped: true })).toBeNull();
    expect(readerHint({ ...audio, timed: false })).toContain("chưa thu thành sách nói");
  });
});

describe("dòng dưới tên cuốn trong 'Nghe cuốn khác'", () => {
  const book = (heardSeconds: number) => ({ duration: 7200, chaptersTotal: 12, complete: true, progress: { heardSeconds, totalSeconds: 7200 } });

  it("nghe dở thì nói tiến độ, chưa nghe thì nói độ dài", () => {
    expect(otherBookLine(book(720))).toBe("Đã nghe 10% cả cuốn · còn 1 giờ 48 phút");
    expect(otherBookLine(book(0))).toBe("Chưa nghe · 2 giờ");
    expect(otherBookLine({ ...book(0), duration: 0 })).toBe("Chưa nghe · 12 chương");
  });
});
