import { describe, expect, it } from "vitest";
import { extendGestureText } from "./extendGesture";

describe("extendGestureText", () => {
  it("says what the listener can actually do on each kind of device", () => {
    expect(extendGestureText(false)).toBe("chạm phím hoặc chuột");
    expect(extendGestureText(true)).toBe("chạm màn hình");
  });
});
