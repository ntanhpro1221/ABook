import { describe, expect, it } from "vitest";
import { excerpt, formatFingerprint, formatSize, licenseLabel, shownReading } from "./format";

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
});
