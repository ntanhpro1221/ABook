import { afterEach, describe, expect, it, vi } from "vitest";
import { automaticSleepAllowed, NIGHT_IDLE_MS, readLocalSystemIdleMs } from "./sleepActivity";
import { sleepExtended, sleepFrom, remoteSleepAfter, remoteSleepCommand } from "./sleep";

afterEach(() => vi.unstubAllGlobals());
describe("automatic timer evidence", () => {
  it("night schedule waits for OS and player idleness", () => {
    expect(automaticSleepAllowed(119_999, 1_000_000, NIGHT_IDLE_MS)).toBe(false);
    expect(automaticSleepAllowed(1_000_000, 119_999, NIGHT_IDLE_MS)).toBe(false);
    expect(automaticSleepAllowed(120_000, 120_000, NIGHT_IDLE_MS)).toBe(true);
  });
  it.each([null, NaN, Infinity, -1])("unknown or invalid OS evidence %s cannot arm", value => {
    expect(automaticSleepAllowed(value, 10_000_000, NIGHT_IDLE_MS)).toBe(false);
  });
  it.each(["media", "bluetooth", "notification", "widget", "volume", "seek", "chapter", "pointer", "remote"])("%s input restarts the idle interval", () => {
    expect(automaticSleepAllowed(10_000_000, 0, NIGHT_IDLE_MS)).toBe(false);
  });
  it("missing idle interval and clock rollback cannot arm a night schedule", () => {
    expect(automaticSleepAllowed(10_000_000, 10_000_000, 0)).toBe(false);
    expect(automaticSleepAllowed(10_000_000, -1, NIGHT_IDLE_MS)).toBe(false);
  });
  it("a remote browser never uses the server's OS idle time", async () => {
    vi.stubGlobal("window", { location: { hostname: "192.168.1.8" } });
    expect(await readLocalSystemIdleMs()).toBeNull();
  });
});
describe("explicit timer routes", () => {
  it("stale notification extension and shake without a timer cannot arm", () => {
    expect(sleepExtended({ kind: "off" }, 10, true, 1000)).toEqual({ kind: "off" });
  });
  it("manual minutes, chapter mode and remote commands require an explicit request", () => {
    expect(sleepFrom({ kind: "chapter" }, true, 1000)).toEqual({ kind: "chapter" });
    expect(sleepFrom({ kind: "minutes", minutes: 30 }, true, 1000)).toMatchObject({ minutes: 30 });
    expect(remoteSleepAfter(remoteSleepCommand({ kind: "off" }), true)).toBeNull();
    expect(remoteSleepAfter(remoteSleepCommand({ kind: "minutes", minutes: 15 }), true)).toMatchObject({ minutes: 15 });
  });
});
