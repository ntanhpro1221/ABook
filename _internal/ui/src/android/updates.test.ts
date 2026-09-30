import { describe, expect, it } from "vitest";
import { latestRelease, newer, releaseFrom } from "./updates";

describe("newer", () => {
  it("compares versions number by number, not as text", () => {
    expect(newer("0.4.10", "0.4.9")).toBe(true);
    expect(newer("0.4.9", "0.4.10")).toBe(false);
    expect(newer("v0.5.0", "0.4.10")).toBe(true);
    expect(newer("0.4.10", "0.4.10")).toBe(false);
    expect(newer("0.4.10.1", "0.4.10")).toBe(true);
  });
});

describe("releaseFrom", () => {
  const reply = {
    tag_name: "v0.4.10",
    html_url: "https://github.com/ntanhpro1221/ABook/releases/tag/v0.4.10",
    assets: [
      { name: "ABook_0.4.10_x64-setup.exe", browser_download_url: "https://github.com/ntanhpro1221/ABook/releases/download/v0.4.10/ABook_0.4.10_x64-setup.exe" },
      { name: "ABook_0.4.10.apk", browser_download_url: "https://github.com/ntanhpro1221/ABook/releases/download/v0.4.10/ABook_0.4.10.apk" },
    ],
  };

  it("finds the version, the page and the APK of the release", () => {
    expect(releaseFrom(reply)).toEqual({
      version: "0.4.10",
      page: "https://github.com/ntanhpro1221/ABook/releases/tag/v0.4.10",
      apk: "https://github.com/ntanhpro1221/ABook/releases/download/v0.4.10/ABook_0.4.10.apk",
    });
  });

  it("keeps the page when a release has no APK, and refuses an odd reply", () => {
    expect(releaseFrom({ ...reply, assets: [] })?.apk).toBeNull();
    expect(releaseFrom({ message: "API rate limit exceeded" })).toBeNull();
    expect(releaseFrom(null)).toBeNull();
  });
});

describe("latestRelease", () => {
  it("asks GitHub at most once a day and falls back to the last answer offline", async () => {
    const store = new Map<string, string>();
    Object.assign(globalThis, {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => void store.set(key, value),
        clear: () => store.clear(),
      },
    });
    let calls = 0;
    const answer = { tag_name: "v0.4.10", html_url: "https://github.com/ntanhpro1221/ABook/releases/tag/v0.4.10", assets: [] };
    const online = (async () => {
      calls += 1;
      return new Response(JSON.stringify(answer), { status: 200 });
    }) as unknown as typeof fetch;
    const offline = (async () => {
      throw new TypeError("mất mạng");
    }) as unknown as typeof fetch;
    expect((await latestRelease(online, 1_000))?.version).toBe("0.4.10");
    expect((await latestRelease(online, 1_000 + 3600 * 1000))?.version).toBe("0.4.10");
    expect(calls).toBe(1);
    expect((await latestRelease(offline, 1_000 + 30 * 3600 * 1000))?.version).toBe("0.4.10");
  });
});
