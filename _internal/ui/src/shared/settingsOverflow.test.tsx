import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ prefs: { libraryRoot: "D:/Thu-vien-sach/rat-dai/khong-co-dau-cach/de-tran-ngang", theme: "system" } }));
vi.mock("@/studio/data", async (original) => ({
  ...(await original<typeof import("@/studio/data")>()),
  usePreferences: () => ({ data: h.prefs, update: vi.fn() }),
  pickFolder: vi.fn(),
  useAppInfo: () => ({ data: { dialogs: true, remote: false, version: "0.0.0" } }),
  useVoices: () => ({ data: [] }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }));
vi.mock("@/listen/VoiceSettings", () => ({ VoiceSettings: () => null, useDefaultVoiceName: () => "" }));
vi.mock("@/studio/musicImport", () => ({ hasNativeMusicImport: () => true, importMusic: vi.fn() }));
import { SettingsScreen as DesktopSettings } from "@/desktop/SettingsScreen";
import { SettingsAt } from "./settingsAt";
import { MyMusicSection } from "@/listen/MyMusic";

// Trang Cài đặt ở 320 px, chữ 32 px không tràn ngang (soát a102, tiếp V5 của a100): nút và liên kết dài xuống dòng, chữ không bị cắt.
// Đo thật ở a100: các nhóm lựa chọn đã gọn, còn tràn trang 448-491 px vì những phần tử dưới đây.
beforeAll(() => {
  Object.assign(globalThis, {
    window: Object.assign(new EventTarget(), {
      location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
      matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    }),
  });
});

const render = (node: React.ReactElement) => renderToStaticMarkup(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);

/** Thẻ mở của phần tử `tag` mà chữ (sau các thẻ mở / biểu tượng lồng đầu) bắt đầu bằng `text`. */
function opening(html: string, tag: string, text: string): string {
  for (const match of html.matchAll(new RegExp(`<${tag}(?=[\\s>])[^>]*>`, "g"))) {
    const rest = html.slice(match.index + match[0].length).split(`</${tag}>`)[0].replace(/<[^>]+>/g, "").trim();
    if (rest.startsWith(text)) return match[0];
  }
  throw new Error(`không thấy <${tag}> "${text}": ${html.slice(html.indexOf(text) - 300, html.indexOf(text) + 40)}`);
}

/** Nút/liên kết dài không được `whitespace-nowrap`, không rộng hơn khung và bẻ được chuỗi liền (đường dẫn, địa chỉ). */
function expectWraps(tag: string) {
  expect(tag, tag).toMatch(/\bwhitespace-normal\b/);
  expect(tag, tag).not.toMatch(/\bwhitespace-nowrap\b/);
  expect(tag, tag).toMatch(/\bmax-w-full\b/);
  expect(tag, tag).toMatch(/\[overflow-wrap:anywhere\]/);
}

describe("Cài đặt trên máy tính: không tràn ngang ở 320 px / chữ 32 px", () => {
  const html = render(<SettingsAt group="advanced" screen={<DesktopSettings />} />);

  it("nút Đổi thư mục xuống dòng và hàng thư mục được xuống hàng", () => {
    const button = opening(html, "button", "Đổi thư mục");
    expectWraps(button);
    expect(button).toMatch(/\bh-auto\b/);
    expect(html).toMatch(/<div class="[^"]*\bflex-wrap\b[^"]*"><div class="[^"]*\bmin-w-0\b[^"]*"><svg/);
  });

  it("nút Thành phần sử dụng xuống dòng", () => {
    expect(opening(html, "button", "Thành phần sử dụng")).toContain("disclosure-row");
    expect(html).toMatch(/class="[^"]*\[overflow-wrap:anywhere\][^"]*">Thành phần sử dụng/);
  });

  it("liên kết github cắt đúng chỗ thay vì đẩy trang rộng ra", () => {
    const link = opening(html, "a", "github.com/ntanhpro1221/ABook");
    expect(link).toMatch(/\[overflow-wrap:anywhere\]/);
  });
});

describe("Nhạc của tôi (cả hai máy)", () => {
  it("nút Thêm nhạc của bạn xuống dòng", () => {
    expectWraps(opening(render(<MyMusicSection />), "button", "Thêm nhạc của bạn"));
  });
});
