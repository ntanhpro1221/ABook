import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { renderToString } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import type { ListenBook } from "@/listen/model";
import { levelOptions, levelText, MUSIC_LEVELS } from "./musicLevels";

// Mức -28 dB kèm lời "rõ lời" (MIX_QA mục 7.1): người nghe thấy ngay mức nào để nghe rõ lời nhất, ở nút mức của trình phát,
// ô chọn của hộp "Sửa sách" và ô chọn tab Nhạc nền của Studio. Dựng bằng react-dom/server như settingsScreens.test.tsx.

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

describe("lời kèm mức nhạc", () => {
  it("chỉ mức -28 có lời rõ lời", () => {
    expect(MUSIC_LEVELS.map(([value, name]) => levelText(value, name))).toEqual([
      "To",
      "Hơi to",
      "Vừa (mặc định)",
      "Nhỏ",
      "Rất nhỏ (rõ lời)",
    ]);
    expect(levelOptions(-18).map(([value, name]) => levelText(value, name))).toContain("Rất nhỏ (rõ lời)");
  });

  it("nút mức của trình phát hiện lời dưới tên mức", async () => {
    const { LevelButtons } = await import("@/listen/PlayerViews");
    const html = wrap(<LevelButtons level={-20} disabled={false} onChange={() => undefined} />);
    expect(html).toContain("Rất nhỏ");
    expect(html).toContain("rõ lời");
    expect(html.match(/rõ lời/g)).toHaveLength(1);
  });

  it("ô chọn mức của hộp Sửa sách có lời", async () => {
    const { MusicSection } = await import("@/listen/EditBook");
    const client = new QueryClient();
    client.setQueryData(["listen", "edit-music", "sach"], { hasMusic: true, enabled: true, levelDb: -20, defaultLevelDb: -20, cues: [] });
    const html = wrap(<MusicSection book={{ id: "sach" } as ListenBook} />, client);
    expect(html).toMatch(/<option[^>]*value="-28"[^>]*>Rất nhỏ \(rõ lời\)<\/option>/);
  });
});
