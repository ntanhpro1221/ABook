import { readFileSync } from "node:fs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { renderToString } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";
import { loadThirdParty, parseThirdParty } from "./thirdParty";
import { TooltipProvider } from "./ui";
import { SettingsAt } from "./settingsAt";

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
  return renderToString(<QueryClientProvider client={new QueryClient()}><TooltipProvider>{children}</TooltipProvider></QueryClientProvider>);
}

/** Các mục `<section id>` + chữ của tiêu đề `h2` (khối gập - a120 - thì tiêu đề nằm trong nút gập / mở bên trong h2). */
function sections(html: string): Record<string, string> {
  return Object.fromEntries(
    [...html.matchAll(/<section[^>]*id="([^"]+)"[^>]*>[\s\S]*?<h2[^>]*>([\s\S]*?)<\/h2>/g)].map((match) => [match[1], match[2].replace(/<[^>]*>/g, "").trim()]),
  );
}

describe("Cài đặt", () => {
  it("máy tính: Nghe có Nhạc nền với Nhạc của tôi; Nâng cao có Giới thiệu và nút thành phần bên thứ ba", async () => {
    const { SettingsScreen } = await import("@/desktop/SettingsScreen");
    const listen = wrap(<SettingsAt group="listen" screen={<SettingsScreen />} />);
    expect(sections(listen).music).toBe("Nhạc nền");
    expect(listen).toContain("Nhạc của tôi");
    const advanced = wrap(<SettingsAt group="advanced" screen={<SettingsScreen />} />);
    expect(sections(advanced).about).toBe("Giới thiệu");
    expect(advanced).toMatch(/<section[^>]*id="about"[^>]*><h2[^>]*><button[^>]*aria-expanded="false"/); // a120: gập sẵn, vẫn dựng trong trang
    expect(advanced).toContain("Thành phần sử dụng");
  });

  it("máy tính: Giao diện có công tắc phím một chữ cái, tên ngắn và mô tả đọc riêng (soát a31: 2.1.4, tên công tắc 300+ chữ)", async () => {
    const { SettingsScreen } = await import("@/desktop/SettingsScreen");
    const html = wrap(<SettingsAt group="look" screen={<SettingsScreen />} />);
    expect(sections(html).shortcuts).toBe("Phím tắt");
    expect(html).toMatch(/id="letter-shortcuts-name"[^>]*>Phím tắt chữ</);
    const control = html.match(/<button[^>]*id="letter-shortcuts"[^>]*>/)?.[0] ?? "";
    expect(control).toContain('role="switch"');
    expect(control).toContain('aria-labelledby="letter-shortcuts-name"');
    expect(control).toContain('aria-describedby="letter-shortcuts-hint"');
    expect(wrap(<SettingsAt group="listen" screen={<SettingsScreen />} />)).toMatch(/<button[^>]*id="auto-music"[^>]*aria-describedby="auto-music-hint"/);
  });

  it("máy tính có công tắc Tự lùi như điện thoại (soát a100 T1), mô tả đúng luật lùi", async () => {
    const { SettingsScreen } = await import("@/desktop/SettingsScreen");
    const html = wrap(<SettingsAt group="listen" screen={<SettingsScreen />} />);
    const control = html.match(/<button[^>]*id="auto-rewind"[^>]*>/)?.[0] ?? "";
    expect(control).toContain('role="switch"');
    expect(control).toContain('aria-label="Tự lùi"');
    expect(control).toContain('aria-checked="true"'); // mặc định bật
    expect(html).toContain("Nghỉ quá 30 giây thì lùi 5 giây");
    expect(html).not.toContain("Luôn bật");
  });

  it("điện thoại: Nghe có Nhạc nền; Nâng cao có Giới thiệu", async () => {
    const { SettingsScreen } = await import("@/android/SettingsScreen");
    const listen = wrap(<SettingsAt group="listen" screen={<SettingsScreen />} />);
    expect(sections(listen).music).toBe("Nhạc nền");
    expect(listen).toContain("Nhạc của tôi");
    const advanced = wrap(<SettingsAt group="advanced" screen={<SettingsScreen />} />);
    expect(sections(advanced).about).toBe("Giới thiệu");
    expect(advanced).toContain("Thành phần sử dụng");
  });

  it("Giới thiệu trên điện thoại ghi phiên bản đang cài", async () => {
    const { AboutBlock } = await import("@/android/SettingsScreen");
    expect(wrap(<AboutBlock version="0.4.29" />)).toContain("0.4.29");
  });
});

describe("cây Cài đặt (chủ app 23-10: không còn là ma trận)", () => {
  /** Tên các nhóm trên trang gốc, theo thứ tự. */
  const groupNames = (html: string) => [...html.matchAll(/<a[^>]*href="[^"]*\/settings\/([a-z]+)"[^>]*>[\s\S]*?<span class="block text-base[^"]*">([^<]+)</g)].map((match) => [match[1], match[2]]);

  it("trang gốc điện thoại: 6 nhóm, mỗi nhóm một dòng, đúng thứ tự dùng nhiều trước", async () => {
    const { SettingsScreen } = await import("@/android/SettingsScreen");
    const html = wrap(<SettingsAt screen={<SettingsScreen />} />);
    expect(groupNames(html)).toEqual([
      ["voice", "Giọng đọc"],
      ["listen", "Nghe"],
      ["sleep", "Hẹn giờ ngủ"],
      ["look", "Giao diện"],
      ["devices", "Thiết bị"],
      ["advanced", "Nâng cao"],
    ]);
    // Trang gốc chỉ là danh sách: không có công tắc nào.
    expect(html).not.toContain('role="switch"');
    expect(html).toContain("Tự lùi · nhạc tự chọn");
  });

  it("trang gốc máy tính: tối đa 7 nhóm, cùng thứ tự với điện thoại", async () => {
    const { SettingsScreen } = await import("@/desktop/SettingsScreen");
    const names = groupNames(wrap(<SettingsAt screen={<SettingsScreen />} />)).map(([id]) => id);
    expect(names.length).toBeLessThanOrEqual(7);
    const order = ["voice", "listen", "sleep", "look", "devices", "studio", "advanced"];
    expect(names).toEqual(order.filter((id) => names.includes(id)));
    expect(names).toEqual(expect.arrayContaining(["voice", "listen", "sleep", "look", "devices", "advanced"]));
  });

  it("màn con có nút về Cài đặt và tiêu đề là tên nhóm", async () => {
    const { SettingsScreen } = await import("@/android/SettingsScreen");
    const html = wrap(<SettingsAt group="sleep" screen={<SettingsScreen />} />);
    expect(html).toContain('aria-label="Về Cài đặt"');
    expect(html).toMatch(/<h1[^>]*>Hẹn giờ ngủ<\/h1>/);
  });

  it("không mục nào nằm ở hai nhóm (điện thoại)", async () => {
    const { SettingsScreen, PHONE_GROUPS } = await import("@/android/SettingsScreen");
    const seen = new Map<string, string>();
    for (const group of PHONE_GROUPS) {
      const html = wrap(<SettingsAt group={group} screen={<SettingsScreen />} />);
      for (const [, label] of html.matchAll(/<div class="text-\[0.9375rem\] font-medium[^"]*">([^<]+)<\/div>/g)) {
        expect(seen.get(label), `${label} ở cả ${seen.get(label)} và ${group}`).toBeUndefined();
        seen.set(label, group);
      }
    }
    expect(seen.size).toBeGreaterThan(8);
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

  it("người dùng không thấy ghi chú dành cho người bảo trì", async () => {
    const text = await loadThirdParty();
    expect(text).toContain("Ghi chú cho người bảo trì"); // vẫn ở file docs cho người phát hành
    const shown = parseThirdParty(text).flatMap((section) => [section.title, ...section.items.map((item) => item.text)]).join(" | ");
    expect(shown).not.toMatch(/người bảo trì|RELEASING|_internal\/|dây chuyền sản xuất/);
    expect(shown).toMatch(/Xuất sách nói/);
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
