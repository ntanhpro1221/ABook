import { expect, it } from "vitest";
import mix from "../../../abook/webui/assets/music_mix.json";
import { VOICE_STALL_MS, VoiceStall } from "./voiceStall";

// Same cases as Android VoiceStallTest and Qt test_music: the three players share one rule and one constant.
it("the position standing still while the voice plays counts only past the limit", () => {
  const stall = new VoiceStall(10_000);
  expect(stall.update(0, 12, true)).toBe(false);
  expect(stall.update(9_999, 12, true)).toBe(false);
  expect(stall.update(10_000, 12, true)).toBe(true);
  expect(stall.update(60_000, 12, true)).toBe(true);
});

it("the voice moving again, a seek or a pause starts the count over", () => {
  const stall = new VoiceStall(10_000);
  stall.update(0, 12, true);
  expect(stall.update(10_000, 12, true)).toBe(true);
  expect(stall.update(10_500, 12.4, true)).toBe(false); // sound again
  expect(stall.update(20_499, 12.4, true)).toBe(false);
  expect(stall.update(20_500, 12.4, true)).toBe(true);
  expect(stall.update(21_000, 12.4, false)).toBe(false); // listener pause is not a stall
  expect(stall.update(40_000, 12.4, true)).toBe(false);
  expect(stall.update(45_000, 90, true)).toBe(false); // seek
  expect(stall.update(55_000, 90, true)).toBe(true);
});

it("the limit comes from music_mix.json and sits above the longest normal gap measured (8.8 s)", () => {
  expect(VOICE_STALL_MS).toBe(mix.voiceStallFadeAfterSeconds * 1000);
  expect(VOICE_STALL_MS).toBe(10_000);
  expect(VOICE_STALL_MS).toBeGreaterThan(8_800);
});
