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
        expect(galleryState.errors).toEqual([]);
        expect([...galleryState.missing]).toEqual([]);
        expect(container.textContent?.trim().length).toBeGreaterThan(0);
      } finally {
        unmount();
        container.remove();
        // Hộp thoại / menu / thông báo của Radix và sonner gắn vào body: dọn cho mục sau.
        document.body.replaceChildren();
      }
    }, 30_000);
  }
}
