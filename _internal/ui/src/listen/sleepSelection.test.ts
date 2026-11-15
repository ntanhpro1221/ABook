// @vitest-environment happy-dom
import { beforeEach, expect, it } from "vitest";
import { readSleepSelection, saveSleepSelection } from "./sleepSelection";

beforeEach(() => localStorage.clear());
it("keeps the chosen amount across recreation, scoped to book and profile", () => {
  for (const request of [{ kind: "minutes", minutes: 10 }, { kind: "chapter", chapters: 2 }] as const) {
    saveSleepSelection("book", "reader", { request, retained: true });
    expect(readSleepSelection("book", "reader", null).request).toEqual(request);
    expect(readSleepSelection("book", "other", null).request.kind).toBe("off");
    expect(readSleepSelection("other", "reader", null).request.kind).toBe("off");
  }
});
it("restores schedule choices within their night, and remembers explicit cancellation", () => {
  saveSleepSelection("book", undefined, { request: { kind: "minutes", minutes: 30 }, window: "night-a" });
  expect(readSleepSelection("book", undefined, "night-a").request.kind).toBe("minutes");
  expect(readSleepSelection("book", undefined, "night-b").request.kind).toBe("off");
  saveSleepSelection("book", undefined, { request: { kind: "off" }, disabledWindow: "night-a" });
  expect(readSleepSelection("book", undefined, "night-a").disabledWindow).toBe("night-a");
});
