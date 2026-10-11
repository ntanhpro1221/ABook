import { describe, expect, it } from "vitest";
import { etaOf, excerpt, fileName, formatEta, formatFingerprint, formatLengthUp, formatSize, licenseLabel, shownReading } from "./format";

describe("shownReading", () => {
  it("capitalises each word of a name's reading for display", () => {
    expect(shownReading("rên-ta-rô")).toBe("Rên-ta-rô");
    expect(shownReading("Mu-rờ-lốc Cu-ô toa hain")).toBe("Mu-rờ-lốc Cu-ô Toa Hain");
    expect(shownReading("Gờ-ran a-rờ-ca-nít")).toBe("Gờ-ran A-rờ-ca-nít");
    expect(shownReading("ơ-lin")).toBe("Ơ-lin");
  });
});

describe("excerpt", () => {
  it("keeps a short line whole, without its dialogue quotes", () => {
    expect(excerpt("“Đi thôi.”")).toBe("Đi thôi.");
    expect(excerpt("『Ta là ai?』")).toBe("Ta là ai?");
    expect(excerpt("- Chị Dậu đâu rồi?")).toBe("Chị Dậu đâu rồi?");
  });

  it("cuts a long line at a word, not inside one", () => {
    const line = "Cậu ấy nói rằng hôm nay trời sẽ mưa to, nên chúng tôi ở nhà đọc sách cả buổi chiều.";
    const short = excerpt(line);
    expect(short.endsWith("…")).toBe(true);
    expect(short.length).toBeLessThanOrEqual(49);
    expect(line.startsWith(short.slice(0, -1))).toBe(true);
    expect(line[short.length - 1]).toBe(" ");
  });

  it("does not leave a comma before the ellipsis", () => {
    expect(excerpt("Một hai ba bốn năm sáu bảy tám, chín mười mười một mười hai", 32)).toBe("Một hai ba bốn năm sáu bảy tám…");
  });

  it("cuts inside a word only when the line has no early space", () => {
    expect(excerpt("Aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", 10)).toBe("Aaaaaaaaaa…");
  });
});

describe("licenseLabel", () => {
  it("turns the catalog's short codes into readable licences, taking the version from the licence link", () => {
    expect(licenseLabel("by", "https://creativecommons.org/licenses/by/4.0/")).toBe("CC BY 4.0");
    expect(licenseLabel("by", "https://creativecommons.org/licenses/by-sa/3.0/deed.en")).toBe("CC BY-SA 3.0");
    expect(licenseLabel("cc0", "https://creativecommons.org/publicdomain/zero/1.0/")).toBe("CC0 1.0");
  });
  it("does not invent a version when there is no link, and keeps unknown codes as they are", () => {
    expect(licenseLabel("by")).toBe("CC BY");
    expect(licenseLabel("by-sa", "")).toBe("CC BY-SA");
    expect(licenseLabel("cc0")).toBe("CC0");
    expect(licenseLabel("ISC", "https://example.org/isc")).toBe("ISC");
    expect(licenseLabel(undefined)).toBe("");
  });
});

describe("formatFingerprint", () => {
  it("groups the stored hex in fours, upper case, and leaves a grouped one as it is", () => {
    expect(formatFingerprint("ab12cd34ef56")).toBe("AB12 CD34 EF56");
    expect(formatFingerprint("AB12 CD34 EF56")).toBe("AB12 CD34 EF56");
    expect(formatFingerprint("ab12c")).toBe("AB12 C");
  });
  it("shows nothing when there is no fingerprint", () => {
    expect(formatFingerprint("")).toBe("");
    expect(formatFingerprint(undefined)).toBe("");
    expect(formatFingerprint(null)).toBe("");
  });
});

describe("formatSize", () => {
  it("shows megabytes below a gigabyte and one decimal above", () => {
    expect(formatSize(850 * 1024 ** 2)).toBe("850 MB");
    expect(formatSize(3.25 * 1024 ** 3)).toBe("3,3 GB");
    expect(formatSize(4 * 1024 ** 3)).toBe("4 GB");
  });
  it("keeps one decimal under 10 MB and never says 0 MB", () => {
    expect(formatSize(0.5 * 1024 ** 2)).toBe("0,5 MB");
    expect(formatSize(3.25 * 1024 ** 2)).toBe("3,3 MB");
    expect(formatSize(200 * 1024)).toBe("0,2 MB");
    expect(formatSize(20 * 1024)).toBe("20 KB");
    expect(formatSize(10 * 1024 ** 2)).toBe("10 MB");
  });
});

describe("fileName", () => {
  it("keeps only the file name of a Windows or POSIX path", () => {
    expect(fileName("D:\\Sách\\Đã xuất\\Truyện.abook")).toBe("Truyện.abook");
    expect(fileName("/home/a/Truyện.m4b")).toBe("Truyện.m4b");
    expect(fileName("Truyện.abook")).toBe("Truyện.abook");
    expect(fileName("D:/Sách/Bộ/")).toBe("Bộ");
  });
});

describe("formatEta", () => {
  it("chỉ nói sắp xong khi bước đang làm thật sự gần xong", () => {
    expect(formatEta(40, 0.95)).toBe("sắp xong");
    expect(formatEta(40, 0.21)).toBe("còn dưới 2 phút");
    expect(formatEta(40)).toBe("sắp xong");
    expect(formatEta(600, 0.2)).toBe("còn khoảng 10 phút");
  });

  it("chưa có tốc độ (không có ước lượng) thì không nói gì", () => {
    expect(etaOf({ eta: null, progress: { analysis: 0.2, synthesis: 0 } })).toBeNull();
    expect(etaOf({ eta: { phase: "analysis", seconds: 30 }, progress: { analysis: 0.21, synthesis: 0 } })).toBe("pha phân tích còn dưới 2 phút");
    expect(etaOf({ eta: { phase: "synthesis", seconds: 30 }, progress: { analysis: 1, synthesis: 0.97 } })).toBe("pha thu âm sắp xong");
  });

  it("nói rõ ước lượng là của bước nào, để không đọc thành cả cuốn sắp xong", () => {
    expect(etaOf({ eta: { phase: "analysis", seconds: 7200 }, progress: { analysis: 0.4, synthesis: 0 } })).toBe("pha phân tích còn khoảng 2 giờ");
    expect(etaOf({ eta: { phase: "synthesis", seconds: 600 }, progress: { analysis: 1, synthesis: 0.5 } })).toBe("pha thu âm còn khoảng 10 phút");
    // Bước phân tích gần xong vẫn còn thu âm phía sau: câu nói về bước, không hứa về cả cuốn.
    expect(etaOf({ eta: { phase: "analysis", seconds: 20 }, progress: { analysis: 0.97, synthesis: 0 } })).toBe("pha phân tích sắp xong");
  });
});

describe("formatLengthUp (soát a26 L10)", () => {
  it("làm tròn lên như đồng hồ đếm ngược của thanh phát", () => {
    expect(formatLengthUp(129)).toBe("3 phút");
    expect(formatLengthUp(56)).toBe("1 phút");
    expect(formatLengthUp(3600)).toBe("1 giờ");
    expect(formatLengthUp(0)).toBe("0 phút");
  });
});
