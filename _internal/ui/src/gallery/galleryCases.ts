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
        if (platform === "phone" && /\/(book-menu|book-confirm-remove|add-book-[12]|player-(sleep|sleep-active|speed|more|chapters))$/.test(entry.id)) {
          expect(document.querySelector('.motion-sheet[data-state="open"] [data-sheet-handle]')).not.toBeNull();
        }
        if (entry.id.endsWith("player-speed") || entry.id.endsWith("player-full-speed")) {
          expect(document.querySelector('[data-current-choice][aria-pressed="true"]')?.textContent).toBe("1,15×");
        }
        if (entry.id === "desktop/settings-studio") {
          // Hai cột: "Cài đặt" là tiêu đề màn (h1), tên nhóm đang mở là tiêu đề cột phải (h2).
          expect(container.querySelector("h1")?.textContent).toBe("Cài đặt");
          expect(container.querySelector(".settings-page h2")?.textContent).toBe("Studio");
          expect(container.textContent).toContain("Tạm dừng dùng pin");
          expect(container.textContent).toContain("Sách mới");
          expect(container.textContent).toContain("Cách đọc chung");
        }
        // Soát Studio 25-10 (stu140b): mỗi điều dưới đây là một LOẠI lỗi đã sửa ở thành phần chung - giữ cho khỏi quay lại.
        const text = container.textContent ?? "";
        // D2: trạng thái rỗng chỉ nói "chưa có" một lần (phụ đề đầu trang từng lặp lại tiêu đề).
        if (entry.id === "desktop/studio-projects-empty") expect(text.split("Chưa có dự án").length - 1).toBe(1);
        // V10: tên giọng / engine / model không lặp ở từng hàng chương của sách chữ, và không hiện trên đầu trang dự án.
        if (entry.id.endsWith("/book-text")) expect(text).not.toMatch(/\(Edge\)|VieNeu|Giọng đọc của máy/);
        // Phần gập (inert) là chi tiết kỹ thuật được phép giữ tên model; phần đang nhìn thấy thì không.
        if (entry.id.startsWith("desktop/studio-project")) {
          const shown = container.cloneNode(true) as HTMLElement;
          for (const folded of shown.querySelectorAll("[inert]")) folded.remove();
          expect(shown.textContent).not.toMatch(/qwen|Phân tích bằng/i);
        }
        // D12: tab Nhạc nền là các hàng cài đặt (không thẻ viền), Nhật ký không tab lồng.
        if (entry.id === "desktop/studio-music") {
          expect(container.querySelector("section.rounded-xl, section.rounded-2xl")).toBeNull();
          expect(container.querySelector(".settings-row [role=switch]")).not.toBeNull();
        }
        if (entry.id === "desktop/studio-activity") expect(container.querySelector('[role="radiogroup"][aria-label="Kiểu nhật ký"]')).toBeNull();
        // Mục trạng thái phải tới đúng màn, không chỉ dựng được vỏ app.
        if (entry.scenario?.requests) {
          const states = Object.values(entry.scenario.requests);
          if (states.includes("loading")) {
            // CoverSearch nằm trong portal; kiểm đúng hộp đang tải, không tìm trong trang phía sau.
            const content = entry.id.endsWith("book-cover-search")
              ? document.querySelector('[aria-label="Đang tìm ảnh bìa"]')?.closest('[role="dialog"]')
              : container;
            expect(content?.querySelector(".motion-skeleton") ?? null).not.toBeNull();
            // Nút đang gửi vẫn báo bận tại chỗ; vùng nội dung phải dùng khung chờ.
            expect([...(content?.querySelectorAll(".animate-spin") ?? [])].filter(spinner => !spinner.closest("button"))).toEqual([]);
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
