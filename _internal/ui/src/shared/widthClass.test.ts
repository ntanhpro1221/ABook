import { describe, expect, it } from "vitest";
import { widthAtLeast, widthClass } from "./widthClass.generated";

describe("khổ cửa sổ (DESIGN.md 5.5)", () => {
  it("năm khổ theo bề ngang nội dung, mốc thuộc về khổ trên", () => {
    expect(widthClass(0)).toBe("compact");
    expect(widthClass(599)).toBe("compact");
    expect(widthClass(600)).toBe("medium");
    expect(widthClass(839)).toBe("medium");
    expect(widthClass(840)).toBe("expanded");
    expect(widthClass(1199)).toBe("expanded");
    expect(widthClass(1200)).toBe("large");
    expect(widthClass(1599)).toBe("large");
    expect(widthClass(1600)).toBe("extraLarge");
  });

  it("widthAtLeast so với mốc của khổ", () => {
    expect(widthAtLeast(839, "expanded")).toBe(false);
    expect(widthAtLeast(840, "expanded")).toBe(true);
    expect(widthAtLeast(1200, "expanded")).toBe(true);
  });
});
