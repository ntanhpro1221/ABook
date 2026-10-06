import { readFileSync } from "node:fs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { renderToString } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import { loadThirdParty, parseThirdParty } from "./thirdParty";

// Cài đặt máy tính và điện thoại: mục "Nhạc nền" ("Nhạc của tôi" chung mọi cuốn - trước chỉ có trong hộp "Sửa sách") và "Giới thiệu"
// (phiên bản, mã nguồn, thành phần bên thứ ba). Dựng bằng react-dom/server: không cần DOM, hiệu ứng không chạy.

beforeAll(() => {
  const store = new Map<string, string>();
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.localStorage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  } as Storage;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    localStorage: globals.localStorage,
  });
});

function wrap(children: ReactNode) {
  return renderToString(<QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>);
}

/** Các mục `<section id>` + tiêu đề `h2` - đúng thứ mục lục của trang Cài đặt máy tính (SectionIndex) đọc ra. */
function sections(html: string): Record<string, string> {
  return Object.fromEntries(
    [...html.matchAll(/<section[^>]*id="([^"]+)"[^>]*>[\s\S]*?<h2[^>]*>([^<]*)<\/h2>/g)].map((match) => [match[1], match[2]]),
  );
}

describe("Cài đặt", () => {
  it("máy tính có mục Nhạc nền với Nhạc của tôi, và mục Giới thiệu có nút thành phần bên thứ ba", async () => {
    const { SettingsScreen } = await import("@/desktop/SettingsScreen");
    const html = wrap(<SettingsScreen />);
    const found = sections(html);
    expect(found.music).toBe("Nhạc nền");
    expect(found.about).toBe("Giới thiệu");
    expect(html).toContain("Nhạc của tôi");
    expect(html).toContain("Thành phần bên thứ ba");
  });

  it("điện thoại có nhóm Nhạc nền và Giới thiệu", async () => {
    const { SettingsScreen } = await import("@/android/SettingsScreen");
    const html = wrap(<SettingsScreen />);
    const found = sections(html);
    expect(found.music).toBe("Nhạc nền");
    expect(found.about).toBe("Giới thiệu");
    expect(html).toContain("Nhạc của tôi");
    expect(html).toContain("Thành phần bên thứ ba");
  });

  it("Giới thiệu trên điện thoại ghi phiên bản đang cài", async () => {
    const { AboutGroup } = await import("@/android/SettingsScreen");
    expect(wrap(<AboutGroup version="0.4.29" />)).toContain("0.4.29");
  });
});

describe("thành phần bên thứ ba", () => {
  it("gói đúng docs/THIRD_PARTY.md và tách được các mục", async () => {
    const text = await loadThirdParty();
    expect(text).toBe(readFileSync(new URL("../../../docs/THIRD_PARTY.md", import.meta.url)).toString("utf-8"));
    const parsed = parseThirdParty(text);
    expect(parsed.map((section) => section.title)).toContain("App điện thoại (Android)");
    expect(parsed[0].title).toBe("");
    expect(parsed[0].items[0].text).toMatch(/^ABook phát hành theo giấy phép MIT/);
  });

  it("dòng tiếp nối nối vào gạch đầu dòng trước nó", () => {
    const parsed = parseThirdParty("# T\n\n## Mục\n\n- Một\n  hai\n- Ba\n\nĐoạn văn\ntiếp.\n");
    expect(parsed).toEqual([
      {
        title: "Mục",
        items: [
          { text: "Một hai", bullet: true },
          { text: "Ba", bullet: true },
          { text: "Đoạn văn tiếp.", bullet: false },
        ],
      },
    ]);
  });
});
