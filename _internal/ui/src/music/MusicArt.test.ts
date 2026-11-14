import { describe, expect, it } from "vitest";
import cases from "../../../tests/fixtures/music_art/cases.json";
import { base64, binary, bmp, rgb, seedOf } from "../../../desktop_qt/qml/MusicArtRaster.mjs";

describe("canonical artwork bytes", () => {
  for (const item of cases) it(item.link || "empty metadata", async () => {
    const hash = async (bytes: Uint8Array) => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new Uint8Array(bytes).buffer)), (v) => v.toString(16).padStart(2, "0")).join("");
    const output = rgb(item.seed);
    expect(seedOf(item.link, item.info)).toBe(item.seed);
    expect(output.length).toBe(96 * 96 * 3);
    expect(await hash(output)).toBe(item.rgbSha256);
    expect(await hash(bmp(item.seed))).toBe(item.bmpSha256);
    expect(base64(item.seed)).toBe(btoa(binary(item.seed)));
  });
  it("has no clock, network or random state", () => {
    expect(rgb(42)).toEqual(rgb(42));
    expect(rgb(42)).not.toEqual(rgb(43));
  });
});
