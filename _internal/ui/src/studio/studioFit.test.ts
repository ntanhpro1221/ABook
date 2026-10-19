import { describe, expect, it } from "vitest";
import { noStudioLine, studioFit } from "./studioFit";

const GIB = 2 ** 30;

describe("máy có đủ để làm sách nói không (soát a64)", () => {
  it("không có card NVIDIA: không đủ, nói lý do", () => {
    const fit = studioFit(null);
    expect(fit.level).toBe("no");
    expect(noStudioLine(fit.reason!)).toBe(
      "Máy này không làm sách nói được (không có card đồ hoạ NVIDIA, hay driver NVIDIA chưa cài). Bạn vẫn nghe ngay mọi sách.",
    );
  });

  it("chia theo bộ nhớ card: >= 8 GB đủ, 6-8 GB có thể, dưới 6 GB không đủ - card 8 GB báo hơi dưới 8 GiB vẫn là đủ", () => {
    expect(studioFit({ name: "RTX 4060", memory: 7.996 * GIB })).toMatchObject({ level: "ok", line: "Card RTX 4060 (8 GB): đủ để làm sách nói (đã thử trên card 8 GB)." });
    expect(studioFit({ name: "RTX 3060", memory: 12 * GIB }).level).toBe("ok");
    expect(studioFit({ name: "RTX 2060", memory: 5.99 * GIB })).toMatchObject({ level: "maybe" });
    const small = studioFit({ name: "GTX 1650", memory: 4 * GIB });
    expect(small.level).toBe("no");
    expect(noStudioLine(small.reason!)).toContain("card GTX 1650 (4 GB) ít bộ nhớ hơn mức tối thiểu 6 GB");
  });

  it("không đọc được bộ nhớ: chưa biết, không chặn", () => {
    expect(studioFit({ name: "Card lạ", memory: 0 }).level).toBe("maybe");
  });
});
