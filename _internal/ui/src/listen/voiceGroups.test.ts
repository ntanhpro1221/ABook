import { describe, expect, it } from "vitest";
import type { ReadAloudVoice } from "./readAloud";
import { genderLabel, groupedVoices, splitVoiceName, voiceSections } from "./voiceGroups";

const voice = (id: string, name: string, gender = ""): ReadAloudVoice => ({ id, name, provider: id.split(":")[0], online: false, gender });

describe("danh sách giọng ở Cài đặt", () => {
  it("tách tên giọng khỏi tên mô-đun trong ngoặc cuối", () => {
    expect(splitVoiceName("Nhẹ (VieNeu Nano)")).toEqual({ shown: "Nhẹ", module: "VieNeu Nano" });
    expect(splitVoiceName("Hoài My")).toEqual({ shown: "Hoài My", module: null });
  });

  it("gom giọng VieNeu theo mô-đun: tiêu đề phụ một lần, tên giọng không lặp mô-đun", () => {
    const list = [
      voice("vieneu:turbo/A", "A (VieNeu)", "female"),
      voice("vieneu:turbo/B", "B (VieNeu)", "male"),
      ...Array.from({ length: 11 }, (_, index) => voice(`vieneu:nano/N${index}`, `N${index} (VieNeu Nano)`)),
    ];
    const sections = voiceSections(list);
    expect(sections.map((section) => [section.label, section.voices.length])).toEqual([["VieNeu", 2], ["VieNeu Nano", 11]]);
    expect(sections[0].voices.map((item) => item.shown)).toEqual(["A", "B"]);
    expect(sections.flatMap((section) => section.voices).every((item) => !item.shown.includes("("))).toBe(true);
  });

  it("một mô-đun duy nhất thì không cần tiêu đề phụ (tiêu đề nhóm đã nói rồi)", () => {
    const sections = voiceSections([voice("azure:a", "An (Azure Speech)"), voice("azure:b", "Bình (Azure Speech)")]);
    expect(sections).toHaveLength(1);
    expect(sections[0].label).toBeNull();
    expect(sections[0].voices.map((item) => item.shown)).toEqual(["An", "Bình"]);
  });

  it("giọng lẻ có ngoặc hay không có ngoặc giữ nguyên tên", () => {
    const sections = voiceSections([voice("device:1", "Microsoft An (vi-VN)"), voice("device:2", "Microsoft Hoa")]);
    expect(sections).toHaveLength(1);
    expect(sections[0].voices.map((item) => item.shown)).toEqual(["Microsoft An (vi-VN)", "Microsoft Hoa"]);
  });
});

describe("nhóm giọng dùng chung với trình phát", () => {
  it("chia theo nhà cung cấp đúng thứ tự Cài đặt, bỏ nhóm rỗng, nhà cung cấp lạ vào 'Khác'", () => {
    const groups = groupedVoices([voice("device:an", "An", "female"), voice("edge:a", "Hoài My (Edge)", "female"), voice("lạ:x", "X")]);
    expect(groups.map((group) => group.provider)).toEqual(["edge", "device", "other"]);
    expect(groups[2].title).toBe("Khác");
  });

  it("nam / nữ nói bằng tiếng Việt, không biết thì để trống", () => {
    expect(genderLabel("female")).toBe("Nữ");
    expect(genderLabel("male")).toBe("Nam");
    expect(genderLabel(undefined)).toBe("");
  });
});
