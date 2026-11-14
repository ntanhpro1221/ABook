import { describe, expect, it } from "vitest";
import { avatarHash, avatarPattern, avatarCells, voiceAvatarFile } from "./avatar";

describe("portrait contract", () => {
  it("normalizes Vietnamese and uses Unicode code points", () => {
    expect(avatarPattern("Ngọc Linh")).toEqual(avatarPattern("Ngo\u0323c Linh"));
    expect(avatarPattern("😀 An").initials).toBe("😀A");
  });
  it("mirrors the same fifteen bits on each platform", () => {
    for (const { x, y } of avatarCells(avatarHash("Minh") & 32767)) {
      expect(avatarCells(avatarHash("Minh") & 32767)).toContainEqual({ x: 4 - x, y });
    }
    expect(voiceAvatarFile("Minh")).toMatch(/^voice-[0-9a-f]{8}\.webp$/);
  });
});
