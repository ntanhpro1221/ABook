import { describe, expect, it } from "vitest";
import { shortWindow, twoPaneWindow } from "./windowLayout";

describe("window layout", () => {
  it.each([[360, 780, false], [800, 360, true], [640, 320, true], [600, 240, true], [320, 240, false], [840, 900, true]])(
    "%sx%s has intentional panes", (width, height, expected) => expect(twoPaneWindow(width, shortWindow(height))).toBe(expected),
  );
});
