import { describe, expect, it } from "vitest";
import { excerpt, shownReading } from "./format";

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
