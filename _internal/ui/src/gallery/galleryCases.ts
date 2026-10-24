import { expect, it } from "vitest";
import { installPlatform } from "./boot";
import { ENTRIES, type Platform } from "./entries";
import { galleryState } from "./state";

// Phần chung của hai bài thử phòng trưng bày (gallery.phone.dom.test.tsx, gallery.desktop.dom.test.tsx): mọi mục của một nền tảng dựng
// được trên dữ liệu giả, không console.error, không lỗi không bắt, thao tác của mục chạy hết, không gọi tới đường / phương thức chưa giả.

export function galleryCases(platform: Platform): void {
  // Trình duyệt đánh dấu lời hứa `animation.finished` là "đã xử lý" (huỷ chuyển động không thành lỗi không bắt); happy-dom thì không.
  const cancel = Animation.prototype.cancel;
  Animation.prototype.cancel = function (this: Animation) {
    this.finished?.catch(() => undefined);
    cancel.call(this);
  };
  // Thế giới giả TRƯỚC khi mã app nạp (mountApp nạp bằng import động).
  installPlatform(platform);
  const media = window.matchMedia.bind(window);
  window.matchMedia = query => query.trim() === "(max-width: 640px)"
    ? { ...media(query), matches: platform === "phone", addEventListener() {}, removeEventListener() {} } as MediaQueryList
    : media(query);
  const entries = ENTRIES.filter((entry) => entry.platform === platform);

  it("danh mục: mã mục duy nhất, đúng tiền tố nền tảng", () => {
    expect(entries.length).toBeGreaterThan(10);
    expect(new Set(ENTRIES.map((entry) => entry.id)).size).toBe(ENTRIES.length);
    for (const entry of entries) expect(entry.id.startsWith(`${platform}/`)).toBe(true);
  });

  for (const entry of entries) {
    it(`${entry.id} - ${entry.title}`, async () => {
      const { runEntry } = await import("./run");
      const container = document.createElement("div");
      document.body.append(container);
      const unmount = await runEntry(entry, "light", container, { quiet: 120 });
      try {
        expect(galleryState.errors, galleryState.errors.join("\n")).toEqual([]);
        expect([...galleryState.missing]).toEqual([]);
        expect(container.textContent?.trim().length).toBeGreaterThan(0);
        if (platform === "phone" && /\/(book-menu|book-confirm-remove|add-book-[12]|player-(sleep|sleep-active|speed|more|chapters|bookmarks))$/.test(entry.id)) {
          expect(document.querySelector('.motion-sheet[data-state="open"] [data-sheet-handle]')).not.toBeNull();
        }
        if (entry.id.endsWith("player-speed") || entry.id.endsWith("player-full-speed")) {
          expect(document.querySelector('[data-current-choice][aria-pressed="true"]')?.textContent).toBe("1,15×");
        }
        if (entry.id === "desktop/settings-studio") {
          expect([...container.querySelectorAll("h1")].at(-1)?.textContent).toBe("Studio");
          expect(container.textContent).toContain("Tạm dừng dùng pin");
          expect(container.textContent).toContain("Sách mới");
          expect(container.textContent).toContain("Cách đọc chung");
        }
        // Mục trạng thái phải tới đúng màn, không chỉ dựng được vỏ app.
        if (entry.scenario?.requests) {
          const states = Object.values(entry.scenario.requests);
          if (states.includes("loading")) {
            expect(container.querySelector(".motion-skeleton")).not.toBeNull();
            expect(container.querySelector("main .animate-spin")).toBeNull();
          }
          if (states.includes("error")) {
            expect(container.querySelector('[role="alert"]')?.textContent).toContain("Thử lại");
          }
        }
        if (entry.id.endsWith("offline-library")) {
          expect(container.querySelector('[role="status"]')?.textContent).toContain("Mất mạng");
          expect(container.querySelector("main button")).not.toBeNull();
        }
      } finally {
        unmount();
        container.remove();
        // Hộp thoại / menu / thông báo của Radix và sonner gắn vào body: dọn cho mục sau.
        document.body.replaceChildren();
      }
    }, 30_000);
  }
}
