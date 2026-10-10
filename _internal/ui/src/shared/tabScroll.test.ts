import { describe, expect, it } from "vitest";
import { revealedScroll, wheelScroll } from "./tabScroll";

describe("wheelScroll", () => {
  it("turns a plain downward wheel into a sideways scroll while there is more to scroll", () => {
    expect(wheelScroll(0, 100, 0, 347, 686)).toBe(100);
    expect(wheelScroll(0, -60, 200, 347, 686)).toBe(140);
  });

  it("stops at the ends instead of swallowing the wheel, so the page can scroll", () => {
    expect(wheelScroll(0, 100, 339, 347, 686)).toBeNull();
    expect(wheelScroll(0, -100, 0, 347, 686)).toBeNull();
    expect(wheelScroll(0, 500, 300, 347, 686)).toBe(339);
    expect(wheelScroll(0, 100, 338.87, 347, 686)).toBeNull();
  });

  it("leaves Ctrl+wheel to the browser: that is zoom, not scrolling", () => {
    expect(wheelScroll(0, 100, 0, 347, 686)).toBe(100);
    expect(wheelScroll(0, 100, 0, 347, 686, true)).toBeNull();
    expect(wheelScroll(0, -100, 200, 347, 686, true)).toBeNull();
  });

  it("leaves a row that fits alone, and a wheel that is already sideways", () => {
    expect(wheelScroll(0, 100, 0, 776, 776)).toBeNull();
    expect(wheelScroll(120, 10, 0, 347, 686)).toBeNull();
    expect(wheelScroll(0, 0, 0, 347, 686)).toBeNull();
  });
});

describe("revealedScroll", () => {
  it("does nothing for a tab already in view", () => {
    expect(revealedScroll(100, 80, 0, 347, 36)).toBeNull();
  });

  it("brings a tab hidden on the right into view with room for the fade", () => {
    expect(revealedScroll(560, 90, 0, 347, 36)).toBe(339);
  });

  it("brings a tab hidden on the left into view, never below zero", () => {
    expect(revealedScroll(120, 80, 200, 347, 36)).toBe(84);
    expect(revealedScroll(10, 80, 200, 347, 36)).toBe(0);
  });
});
