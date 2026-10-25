import { describe, expect, it } from "vitest";
import { bookProgressText, chapterSubline, caughtUpDetail, caughtUpLine, chapterOpenProblem, retryChapterText, keepTogether, nextChapterLabel, otherBookLine, partialBookLine, PREPARING_VOICE, PREPARING_VOICE_AFTER_MS, primaryListenLabel, readerHint, resumeWhere, tapVerb, textBookLine, toggleLabel, unquoted } from "./labels";

const fresh = { playingHere: false, finished: false, point: { title: "Chương 1", at: 0 }, heard: 0, textOnly: false };

describe("nút chính của trang sách", () => {
  it("sách mới: 'Nghe', cả sách nói lẫn sách chỉ có chữ", () => {
    expect(primaryListenLabel({ ...fresh, textOnly: true })).toBe("Nghe");
    expect(primaryListenLabel(fresh)).toBe("Nghe");
  });

  it("có tiến độ: 'Nghe tiếp · Chương N' - chỉ chương, không giờ phút", () => {
    expect(primaryListenLabel({ ...fresh, textOnly: true, point: { title: "Chương 3", at: 724 }, heard: 900 })).toBe("Nghe tiếp · Chương 3");
    expect(resumeWhere("Chương 3", 724)).toBe("Chương 3 · 12:04");
    expect(primaryListenLabel({ ...fresh, point: { title: "Chương 2", at: 0 }, heard: 300 })).toBe("Nghe tiếp · Chương 2");
    expect(primaryListenLabel({ ...fresh, point: null, heard: 300 })).toBe("Nghe tiếp");
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

  it("hết sách: nói đã hết, không để một con số như 98%", () => {
    expect(bookProgressText({ ...base, whole: true, heard: 3234, finished: true })).toBe("Đã nghe hết cả cuốn");
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
  });
});

describe("lời nhắc màn đọc", () => {
  const base = { textOnly: true, canSpeak: true, timed: false, tapped: false, coarse: false, wish: false };

  it("không lặp trạng thái chỉ có chữ, vẫn hướng dẫn đầy đủ chuột phải", () => {
    for (const canSpeak of [true, false]) for (const tapped of [true, false]) {
      expect(readerHint({ ...base, canSpeak, tapped })?.toLowerCase()).not.toContain("chỉ có chữ");
    }
    expect(readerHint({ ...base, readings: true })).toContain("Bấm chuột phải vào chữ để sửa cách đọc.");
    expect(readerHint({ ...base, canSpeak: false })).toBe("Máy này chưa có giọng đọc.");
  });

  it("bấm với chuột, chạm với màn cảm ứng", () => {
    expect(tapVerb(false)).toBe("Bấm");
    expect(tapVerb(true)).toBe("Chạm");
    expect(readerHint(base)).toContain("Bấm chữ");
    expect(readerHint({ ...base, coarse: true })).toContain("Chạm chữ");
  });

  it("không đổi khi giọng máy đã đọc xong đoạn đầu (kịch bản có mốc)", () => {
    expect(readerHint({ ...base, timed: true })).toBe(readerHint(base));
    expect(readerHint({ ...base, tapped: true })).toBe("Nghe bằng giọng đọc.");
  });

  it("sách nói của Studio", () => {
    const audio = { ...base, textOnly: false, canSpeak: false, timed: true };
    expect(readerHint(audio)).toBe("Bấm chữ để nghe từ đó.");
    expect(readerHint({ ...audio, tapped: true })).toBeNull();
    expect(readerHint({ ...audio, timed: false })).toContain("Chưa có audio");
  });

  it("quyền sửa câu: nhắc đúng người nói, cách đọc và thu lại", () => {
    const audio = { ...base, textOnly: false, canSpeak: false, timed: true, wish: true };
    expect(readerHint(audio)).toBe("Bấm chữ để nghe từ đó. “Sửa câu này”: đổi người nói, cách đọc hoặc thu lại.");
    expect(readerHint({ ...audio, wish: false })).not.toContain("Sửa câu này");
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

describe("keepTogether", () => {
  it("keeps the word and the number of a chapter on one line", () => {
    expect(keepTogether("Chương 1")).toBe("Chương\u00a01");
    expect(keepTogether("Chương 12 · Bến phà")).toBe("Chương\u00a012 · Bến phà");
    expect(keepTogether("Bến phà lúc bình minh")).toBe("Bến phà lúc bình minh");
  });
});

describe("sách chưa đủ chương mà không máy nào thu", () => {
  it("chỉ hứa 'khi máy làm xong' lúc có máy đang thu; không thì nói điều chắc chắn", () => {
    expect(caughtUpDetail(true)).toContain("khi máy làm xong");
    expect(caughtUpDetail(false)).not.toContain("máy làm xong");
    expect(caughtUpDetail()).toBe("Các chương sau chưa có audio.");
    expect(caughtUpLine()).toBe("Đã nghe hết phần đã có - các chương sau chưa có audio");
  });

  it("dòng trạng thái cho số chương đã thu, không nói việc thu đang dừng", () => {
    expect(partialBookLine(1, 2)).toBe("Sách này có 1/2 chương đã thu - các chương sau chưa có audio");
    expect(partialBookLine(1, 2)).not.toContain("đang dừng");
  });
});

describe("dòng phụ của chương", () => {
  const chapter = { title: "Chương 8", subtitle: "", available: false, duration: 0, state: "text" as const };

  it("chương chỉ có chữ không ghi giọng hay tên bộ máy: chữ giống nhau trên mọi hàng thì không ghi trên hàng nào", () => {
    expect(chapterSubline(chapter, false)).toBe("");
    expect(chapterSubline({ ...chapter, subtitle: "Mùi giấy cũ", title: "Chương 4" }, false)).toBe("Chương 4");
    expect(chapterSubline(chapter, false)).not.toMatch(/Edge|VieNeu|Giọng đọc/);
  });

  it("chương có audio nói độ dài, chương chưa có nói đang thu hay chưa có", () => {
    const audio = { ...chapter, state: null };
    expect(chapterSubline({ ...audio, available: true, duration: 1560, subtitle: "Mùi giấy cũ", title: "Chương 4" }, false)).toBe("Chương 4 · 26 phút");
    expect(chapterSubline(audio, true)).toBe("Đang thu âm…");
    expect(chapterSubline(audio, false)).toBe("Chưa có audio");
  });
});

describe("lời nhắc màn đọc: giữ chữ ở cả hai loại sách", () => {
  it("sách nói sửa được cũng nhắc giữ chữ đọc sai, cùng câu với sách chữ", () => {
    const audio = { textOnly: false, canSpeak: false, timed: true, tapped: false, coarse: true, wish: true, readings: true };
    expect(readerHint(audio)).toContain("Giữ chữ để sửa cách đọc.");
    const text = { ...audio, textOnly: true, canSpeak: true, wish: false };
    expect(readerHint(text)).toContain("Giữ chữ để sửa cách đọc.");
  });

  it("chuột phải trên máy tính", () => {
    const audio = { textOnly: false, canSpeak: false, timed: true, tapped: false, coarse: false, wish: true, readings: true };
    expect(readerHint(audio)).toContain("Bấm chuột phải vào chữ để sửa cách đọc.");
  });
});

describe("chờ giọng đọc", () => {
  it("chỉ nói 'Đang chuẩn bị giọng đọc…' khi chờ quá ~1,5 giây", () => {
    expect(PREPARING_VOICE_AFTER_MS).toBeGreaterThanOrEqual(1000);
    expect(PREPARING_VOICE_AFTER_MS).toBeLessThanOrEqual(2000);
  });
});

describe("unquoted (soát a26 L6: dấu trang hiện ““…””)", () => {
  it("bỏ ngoặc của chính câu thoại trước khi bọc ngoặc trích", () => {
    expect(unquoted("“Đi thôi.”")).toBe("Đi thôi.");
    expect(unquoted("Lucien nhìn Natasha.")).toBe("Lucien nhìn Natasha.");
    expect(unquoted(" «Ừ» ")).toBe("Ừ");
  });
});

// Soát a27 lỗi 12: máy kia tắt mà chữ chương chưa về - nói máy ấy không trả lời, không nói "chương không còn", và không chờ thử lại ba lần.
describe("chapterOpenProblem", () => {
  it("names the silent machine instead of a missing chapter", () => {
    const off = Object.assign(new Error("Máy A không trả lời (tắt hay mất mạng). Chữ chương này chưa có trên máy này"), { status: 503 });
    expect(chapterOpenProblem(off)).toBe("Máy A không trả lời (tắt hay mất mạng). Chữ chương này chưa có trên máy này.");
    expect(chapterOpenProblem(Object.assign(new Error("Không có chương này"), { status: 404 }))).toBe("Chương có thể không còn trong sách.");
    expect(chapterOpenProblem(null)).toBe("Chương có thể không còn trong sách.");
  });
  it("does not retry a missing chapter or a silent machine", () => {
    expect(retryChapterText(0, { status: 503 })).toBe(false);
    expect(retryChapterText(0, { status: 404 })).toBe(false);
    expect(retryChapterText(0, { status: 500 })).toBe(true);
    expect(retryChapterText(2, { status: 500 })).toBe(false);
  });
});
