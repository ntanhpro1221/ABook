import { describe, expect, it } from "vitest";
import type { Voice } from "./api";
import { narratorIsAuto, recommendedFor } from "./narratorChoice";

const voices: Voice[] = [
  { name: "Giọng A", gender: "Nam", region: "Bắc", style: "Kể chuyện", recommended: true, preview: true },
  { name: "Giọng B", gender: "Nữ", region: "Bắc", style: "Kể chuyện", recommended: true, preview: true },
  { name: "Giọng C", gender: "Nữ", region: "Nam", style: "Tự nhiên", recommended: false, preview: true },
];

describe("narratorIsAuto", () => {
  it("máy chọn giọng dẫn khi có người kể “tôi” và người dùng chưa chọn", () => {
    expect(narratorIsAuto({ firstPerson: "Mai" }, undefined, voices)).toBe(true);
  });
  it("sách ngôi ba không có gì để máy chọn theo", () => {
    expect(narratorIsAuto({ firstPerson: "  " }, undefined, voices)).toBe(false);
  });
  it("người dùng đã bấm một giọng thì là lựa chọn của họ", () => {
    expect(narratorIsAuto({ firstPerson: "Mai", narratorPicked: true }, undefined, voices)).toBe(false);
  });
  it("giọng mặc định người dùng đặt trong Cài đặt cũng là lựa chọn; giọng đã không còn thì không", () => {
    expect(narratorIsAuto({ firstPerson: "Mai" }, "Giọng C", voices)).toBe(false);
    expect(narratorIsAuto({ firstPerson: "Mai" }, "Giọng đã xoá", voices)).toBe(true);
  });
  it("sách nối tiếp và sửa thiết lập mang giọng kể của sách trước", () => {
    expect(narratorIsAuto({ firstPerson: "Mai", seed: { id: "x" } }, undefined, voices)).toBe(false);
    expect(narratorIsAuto({ firstPerson: "Mai", replaces: { id: "x" } }, undefined, voices)).toBe(false);
  });
});

describe("recommendedFor", () => {
  it("chọn giọng đề xuất của đúng giới", () => {
    expect(recommendedFor(voices, "male")).toBe("Giọng A");
    expect(recommendedFor(voices, "female")).toBe("Giọng B");
  });
  it("chưa rõ giới hay chưa có danh sách giọng thì không đề xuất", () => {
    expect(recommendedFor(voices, undefined)).toBeUndefined();
    expect(recommendedFor(undefined, "female")).toBeUndefined();
  });
});
