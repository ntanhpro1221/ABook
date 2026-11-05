import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import type { ReactNode } from "react";
import { renderToString } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import mix from "../../../abook/webui/assets/music_mix.json";
import type { ListenBook } from "@/listen/model";
import { DEFAULT_LEVEL_DB, LEVEL_MAX_DB, LEVEL_MIN_DB, LEVEL_STEP_DB, clampLevel, levelLabel, levelNumber } from "./musicLevels";

// Thanh trượt "Mức nhạc nền": miền / bước / mặc định đọc từ music_mix.json (một file cho máy chủ, Android, Qt), chữ từng mức theo bảng chung
// tests/fixtures/settings/ranges.json "musicLevel" - MusicLevelsTest.kt và test_music.cpp đọc cùng bảng. Dựng bằng react-dom/server như settingsScreens.test.tsx.
const ranges = JSON.parse(readFileSync(new URL("../../../tests/fixtures/settings/ranges.json", import.meta.url)).toString("utf8")) as {
  musicLevel: { labels: [number, string, string][]; clamped: [number, number][] };
};

beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

function wrap(children: ReactNode, client = new QueryClient()) {
  return renderToString(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}

describe("mức nhạc nền", () => {
  it("miền, bước, mặc định là số của music_mix.json", () => {
    expect([LEVEL_MIN_DB, LEVEL_MAX_DB, LEVEL_STEP_DB, DEFAULT_LEVEL_DB]).toEqual([mix.levelMinDb, mix.levelMaxDb, mix.levelStepDb, mix.levelDefaultDb]);
    expect([LEVEL_MIN_DB, LEVEL_MAX_DB, LEVEL_STEP_DB, DEFAULT_LEVEL_DB]).toEqual([-40, -6, 1, -20]);
  });

  it("tên vùng và số của từng mức theo bảng chung", () => {
    for (const [value, label, text] of ranges.musicLevel.labels) {
      expect([value, levelLabel(value)]).toEqual([value, label]);
      expect([value, levelNumber(value)]).toEqual([value, text]);
    }
  });

  it("kẹp ở hai đầu", () => {
    for (const [given, kept] of ranges.musicLevel.clamped) expect([given, clampLevel(given)]).toEqual([given, kept]);
  });

  it("menu Nhạc nền: thanh trượt, không còn nút từng mức", async () => {
    const { MusicLevelRow } = await import("@/listen/PlayerViews");
    const html = wrap(<MusicLevelRow level={-18.5} disabled={false} onChange={() => undefined} />);
    expect(html).toContain('role="slider"');
    expect(html).toContain('aria-valuemin="-40"');
    expect(html).toContain('aria-valuemax="-6"');
    expect(html).toContain('aria-valuetext="Hơi to, -18,5 dB"');
    expect(html).toContain("Về mặc định");
    expect(html).not.toContain("của sách");
    expect(html).not.toContain("aria-pressed");
  });

  it("đúng mặc định thì không có Về mặc định", async () => {
    const { MusicLevelRow } = await import("@/listen/PlayerViews");
    const html = wrap(<MusicLevelRow level={DEFAULT_LEVEL_DB} disabled={false} onChange={() => undefined} />);
    expect(html).toContain("-20 dB (mặc định)");
    expect(html).toContain(">Vừa<");
    expect(html).not.toContain("Về mặc định");
  });

  it("hộp Sửa sách có thanh trượt mức", async () => {
    const { MusicSection } = await import("@/listen/EditBook");
    const client = new QueryClient();
    client.setQueryData(["listen", "edit-music", "sach"], { hasMusic: true, enabled: true, levelDb: -28, defaultLevelDb: -20, cues: [] });
    const html = wrap(<MusicSection book={{ id: "sach" } as ListenBook} />, client);
    expect(html).toContain('aria-valuetext="Rất nhỏ (rõ lời), -28 dB"');
    expect(html).not.toContain("<option");
  });
});
