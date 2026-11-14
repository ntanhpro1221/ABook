import { describe, expect, it } from "vitest";
import { avatarHash, avatarPattern, avatarCells, voiceAvatarFile } from "./avatar";

describe("portrait contract", () => {
  it("normalizes Vietnamese and uses Unicode code points", () => {
    expect(avatarPattern("Ngọc Linh")).toEqual(avatarPattern("Ngo\u0323c Linh"));
    expect(avatarPattern("😀 An").initials).toBe("😀A");
  });
  it("matches the desktop table (abook/avatars.py, AvatarArtTest.kt)", () => {
    const table: [string, string, string, number, string][] = [
      ["Minh", "M", "#675f48", 6477, "voice-f269994d.webp"],
      ["Ngọc Linh", "NL", "#80565e", 3879, "voice-16178f27.webp"],
      ["LUCIEN", "L", "#4c6963", 6245, "voice-c3e21865.webp"],
      ["Vua Lê III", "VL", "#4c6963", 5131, "voice-42d1140b.webp"],
      ["😀 An", "😀A", "#675f48", 32463, "voice-26f3fecf.webp"],
      ["Phạm Tuyên", "PT", "#4c6963", 27855, "voice-fed1eccf.webp"],
    ];
    for (const [name, initials, color, bits, voice] of table) {
      expect(avatarPattern(name)).toMatchObject({ initials, color, bits });
      expect(voiceAvatarFile(name)).toBe(voice);
    }
  });
  it("mirrors the same fifteen bits on each platform", () => {
    for (const { x, y } of avatarCells(avatarHash("Minh") & 32767)) {
      expect(avatarCells(avatarHash("Minh") & 32767)).toContainEqual({ x: 4 - x, y });
    }
    expect(voiceAvatarFile("Minh")).toMatch(/^voice-[0-9a-f]{8}\.webp$/);
  });
});
