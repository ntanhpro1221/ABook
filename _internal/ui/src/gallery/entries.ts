import { click, find, type } from "./actions";
import type { Scenario } from "./state";
import type { StateStory } from "./StateStories";

// Danh mục phòng trưng bày. Mỗi mục = một URL hash ổn định (#/<platform>/<tên>) -> một trang của app thật (`route`, router hash của app)
// trên dữ liệu giả (`scenario`), rồi vài thao tác như người dùng (`act`) để tới đúng trạng thái cần chụp. Thêm mục: thêm một dòng ở đây.

export type Theme = "light" | "dark";
export type Platform = "phone" | "desktop";

export interface Entry {
  /** "phone/library-full": phần sau dấu # của URL, ổn định giữa các lần chạy - tên file ảnh chụp. */
  id: string;
  platform: Platform;
  group: string;
  title: string;
  /** Trang của app (router hash của app), vd "/book/suong-mu-2". */
  route: string;
  scenario?: Partial<Scenario>;
  showcase?: StateStory;
  /** Giờ của đồng hồ giả (ms) nếu khác mặc định. */
  clock?: number;
  /** Tuỳ chọn trình phát của điện thoại (android/settings.ts), thêm vào cạnh chủ đề. */
  phoneSettings?: Record<string, unknown>;
  /** Mục localStorage cần có trước khi app dựng. */
  storage?: Record<string, string>;
  /** Thao tác sau khi trang đã dựng (mở menu, bấm phát...). */
  act?: () => Promise<void>;
}

export const FRAMES: Record<Platform, { width: number; height: number }> = {
  phone: { width: 412, height: 915 },
  desktop: { width: 1440, height: 900 },
};

const SETTINGS_LABELS: Record<string, string> = {
  voice: "Giọng đọc",
  listen: "Nghe",
  sleep: "Hẹn giờ ngủ",
  look: "Giao diện",
  devices: "Thiết bị",
  studio: "Studio",
  advanced: "Nâng cao",
};

const MORNING = Date.UTC(2026, 9, 25, 0, 20); // 7:20 sáng 25-10, giờ Việt Nam

const playerOpen = async () => {
  await click("Mở màn hình đang nghe");
};
const textPlayerMore = async () => {
  await click(/^Nghe/, document.querySelector("main")!);
  await playerOpen(); await click("Thêm tuỳ chọn");
};

const PHONE: Omit<Entry, "platform">[] = [
  { id: "phone/library-full", group: "Thư viện", title: "Thư viện đủ sách", route: "/" },
  { id: "phone/library-shelves", group: "Thư viện", title: "Mở bộ sách", route: "/", act: () => click("Mở bộ Thành Phố Sương Mù").then(() => undefined) },
  { id: "phone/library-search", group: "Thư viện", title: "Tìm sách (không dấu)", route: "/", act: async () => { await click("Tìm sách"); await type("Tìm sách", "suong mu"); } },
  { id: "phone/library-morning", group: "Thư viện", title: "Buổi sáng: thẻ “Tối qua”", route: "/", clock: MORNING, scenario: { night: true } },
  { id: "phone/library-empty", group: "Thư viện", title: "Thư viện rỗng", route: "/", scenario: { library: "empty", paired: false } },
  { id: "phone/library-loading", group: "Thư viện", title: "Đang tải thư viện", route: "/", scenario: { library: "loading" } },
  { id: "phone/library-error", group: "Thư viện", title: "Lỗi đọc thư viện", route: "/", scenario: { library: "error" } },
  { id: "phone/book", group: "Trang sách", title: "Trang sách đang nghe dở", route: "/book/suong-mu-2" },
  { id: "phone/book-menu", group: "Trang sách", title: "Menu của trang sách", route: "/book/suong-mu-2", act: () => click("Thêm việc với sách").then(() => undefined) },
  ...([['new', 'Hồ sơ mới'], ['move', 'Chuyển hồ sơ'], ['rename', 'Đổi tên hồ sơ…'], ['delete', 'Xoá hồ sơ…']] as const).map(([id, label]) => ({
    id: `phone/book-record-${id}`, group: "Trang sách", title: label, route: "/book/suong-mu-2", act: async () => {
      await click("Thêm việc với sách"); await click(label);
    },
  })),
  { id: "phone/book-confirm-remove", group: "Trang sách", title: "Hộp xác nhận xoá khỏi điện thoại", route: "/book/suong-mu-2", act: async () => {
    await click("Thêm việc với sách");
    await click(/^Xoá khỏi điện thoại/);
  } },
  { id: "phone/book-bookmarks", group: "Trang sách", title: "Tab Dấu trang", route: "/book/suong-mu-2", act: () => click(/^Dấu trang, \d+ mục/).then(() => undefined) },
  { id: "phone/book-history", group: "Trang sách", title: "Tab Lịch sử nghe", route: "/book/suong-mu-2", act: () => click("Lịch sử").then(() => undefined) },
  { id: "phone/book-cast", group: "Trang sách", title: "Tab Nhân vật", route: "/book/suong-mu-2", act: () => click("Nhân vật").then(() => undefined) },
  { id: "phone/book-text", group: "Trang sách", title: "Sách chỉ có chữ (EPUB)", route: "/book/gac-xep" },
  { id: "phone/book-streamed", group: "Trang sách", title: "Sách trên máy tính (nghe thẳng)", route: "/book/lang-may" },
  { id: "phone/book-producing", group: "Trang sách", title: "Sách đang làm dở", route: "/book/dong-ho-cat" },
  { id: "phone/toast", group: "Thông báo", title: "Thông báo (toast) “Đang tải về máy”", route: "/book/lang-may", act: async () => {
    await click("Thêm việc với sách");
    await click("Tải về máy");
  } },
  { id: "phone/player-mini", group: "Trình phát", title: "Trình phát mini đang phát", route: "/", act: () => click("Phát", document.querySelector("main")?.nextElementSibling ?? document).then(() => undefined) },
  { id: "phone/player-full", group: "Trình phát", title: "Màn Đang nghe (toàn màn)", route: "/", act: playerOpen },
  { id: "phone/player-sleep", group: "Trình phát", title: "Bảng hẹn giờ ngủ", route: "/", act: async () => {
    await playerOpen();
    await click(/^Hẹn giờ tắt/);
  } },
  { id: "phone/player-speed", group: "Trình phát", title: "Bảng tốc độ đọc", route: "/", act: async () => {
    await playerOpen();
    await click(/^Tốc độ đọc/);
  } },
  { id: "phone/player-sleep-active", group: "Trình phát", title: "Hẹn giờ đang bật", route: "/", act: async () => {
    await playerOpen(); await click(/^Hẹn giờ tắt/); await click("15 phút"); await click(/^Hẹn giờ tắt/);
  } },
  { id: "phone/player-bookmarks", group: "Trình phát", title: "Bảng dấu trang", route: "/", act: async () => {
    await playerOpen(); await click("Thêm tuỳ chọn"); await click("Dấu trang", document.querySelector("[data-player-more]")!);
  } },
  { id: "phone/player-text-more", group: "Trình phát", title: "Tuỳ chọn sách chữ", route: "/book/gac-xep", act: textPlayerMore },
  { id: "phone/player-music", group: "Trình phát", title: "Bảng nhạc nền", route: "/book/gac-xep", act: async () => {
    await textPlayerMore(); await click("Nhạc nền");
  } },
  { id: "phone/player-voice", group: "Trình phát", title: "Bảng giọng đọc", route: "/book/gac-xep", act: async () => {
    await textPlayerMore(); await click(/^Giọng đọc:/);
  } },
  { id: "phone/player-more", group: "Trình phát", title: "Menu “…” của màn Đang nghe", route: "/", act: async () => {
    await playerOpen();
    await click("Thêm tuỳ chọn");
  } },
  { id: "phone/player-chapters", group: "Trình phát", title: "Bảng chương (bảng trượt)", route: "/", act: async () => {
    await playerOpen();
    await click("Chương");
  } },
  { id: "phone/reader", group: "Đọc theo", title: "Đọc theo chương đang nghe", route: "/book/suong-mu-2/read/4" },
  { id: "phone/reader-text", group: "Đọc theo", title: "Chế độ đọc sách chữ", route: "/book/gac-xep/read/2" },
  { id: "phone/add-book-1", group: "Thêm sách", title: "Thêm sách · bước 1: chọn file", route: "/", act: () => click("Thêm sách").then(() => undefined) },
  { id: "phone/add-book-2", group: "Thêm sách", title: "Thêm sách · bước 2: xem trước", route: "/", act: async () => {
    await click("Thêm sách");
    await click(/^Chọn file/);
  } },
  { id: "phone/add-book-3", group: "Thêm sách", title: "Thêm sách · bước 3: đã thêm (toast)", route: "/", act: async () => {
    await click("Thêm sách");
    await click(/^Chọn file/);
    await click("Thêm vào thư viện");
  } },
  { id: "phone/devices", group: "Cài đặt", title: "Thiết bị (đã ghép)", route: "/settings/devices" },
  { id: "phone/devices-unpaired", group: "Cài đặt", title: "Thiết bị (chưa ghép)", route: "/settings/devices", scenario: { paired: false } },
  { id: "phone/studio", group: "Studio", title: "Studio từ xa", route: "/studio" },
  { id: "phone/studio-empty", group: "Studio", title: "Studio chưa ghép máy", route: "/studio", scenario: { paired: false } },
  { id: "phone/library-remote", group: "Thư viện", title: "Sách máy kia trong lưới", route: "/", act: async () => { document.querySelector('[aria-label="Mở Đường Về Làng Mây"]')?.scrollIntoView({ block: "center" }); } },
  { id: "phone/library-download", group: "Thư viện", title: "Tiến độ trên bìa", route: "/", act: async () => { if (find("Tải")) await click("Tải"); document.querySelector('[aria-label="Mở Đường Về Làng Mây"]')?.scrollIntoView({ block: "center" }); } },
  { id: "phone/settings", group: "Cài đặt", title: "Cài đặt (gốc)", route: "/settings" },
  ...(["voice", "listen", "sleep", "look", "advanced"] as const).map((group): Omit<Entry, "platform"> => ({
    id: `phone/settings-${group}`,
    group: "Cài đặt",
    title: `Cài đặt › ${SETTINGS_LABELS[group]}`,
    route: `/settings/${group}`,
  })),
];

const DESKTOP: Omit<Entry, "platform">[] = [
  { id: "desktop/library-full", group: "Thư viện", title: "Thư viện đủ sách", route: "/" },
  { id: "desktop/library-morning", group: "Thư viện", title: "Buổi sáng: thẻ “Tối qua”", route: "/", clock: MORNING, scenario: { night: true } },
  { id: "desktop/library-remote", group: "Thư viện", title: "Sách từ máy ghép", route: "/", scenario: { remoteBooks: true }, act: async () => { document.querySelector('[aria-label="Mở Đường Về Làng Mây"]')?.scrollIntoView({ block: "center" }); } },
  { id: "desktop/library-shelves", group: "Thư viện", title: "Mở bộ sách", route: "/", act: () => click("Mở bộ Thành Phố Sương Mù").then(() => undefined) },
  { id: "desktop/library-search", group: "Thư viện", title: "Tìm sách (không dấu)", route: "/", act: async () => { await click("Tìm sách"); await type("Tìm sách", "hai dang"); } },
  { id: "desktop/library-empty", group: "Thư viện", title: "Thư viện rỗng", route: "/", scenario: { library: "empty", projects: "empty" } },
  { id: "desktop/library-loading", group: "Thư viện", title: "Đang tải thư viện", route: "/", scenario: { library: "loading" } },
  { id: "desktop/library-error", group: "Thư viện", title: "Lỗi đọc thư viện", route: "/", scenario: { library: "error" } },
  { id: "desktop/book", group: "Trang sách", title: "Trang sách đang nghe dở", route: "/book/suong-mu-2" },
  { id: "desktop/book-menu", group: "Trang sách", title: "Menu của trang sách", route: "/book/suong-mu-2", act: () => click("Thêm việc với sách").then(() => undefined) },
  { id: "desktop/book-bookmarks", group: "Trang sách", title: "Tab Dấu trang", route: "/book/suong-mu-2", act: () => click(/^Dấu trang, \d+ mục/).then(() => undefined) },
  { id: "desktop/book-history", group: "Trang sách", title: "Tab Lịch sử nghe", route: "/book/suong-mu-2", act: () => click("Lịch sử").then(() => undefined) },
  { id: "desktop/book-cast", group: "Trang sách", title: "Tab Nhân vật", route: "/book/suong-mu-2", act: () => click("Nhân vật").then(() => undefined) },
  { id: "desktop/book-text", group: "Trang sách", title: "Sách chỉ có chữ (EPUB)", route: "/book/gac-xep" },
  { id: "desktop/book-producing", group: "Trang sách", title: "Sách đang làm dở", route: "/book/dong-ho-cat" },
  { id: "desktop/book-confirm-remove", group: "Trang sách", title: "Hộp xác nhận xoá sách đã nhập", route: "/book/gac-xep", act: async () => {
    await click("Thêm việc với sách");
    await click(/^Xoá khỏi thư viện/);
  } },
  { id: "desktop/toast", group: "Thông báo", title: "Thông báo (toast) sau khi đặt dấu trang", route: "/", act: async () => {
    await click("Thêm tuỳ chọn");
    await click(/^Thêm dấu trang/);
  } },
  { id: "desktop/player-playing", group: "Trình phát", title: "Thanh phát đang phát", route: "/", act: () => click("Phát").then(() => undefined) },
  { id: "desktop/player-full", group: "Trình phát", title: "Màn Đang nghe (toàn màn)", route: "/", act: playerOpen },
  { id: "desktop/player-sleep", group: "Trình phát", title: "Hẹn giờ ngủ", route: "/", act: async () => {
    await click("Thêm tuỳ chọn");
    await click(/^Hẹn giờ tắt/);
  } },
  { id: "desktop/player-more", group: "Trình phát", title: "Menu “…” của thanh phát", route: "/", act: () => click("Thêm tuỳ chọn").then(() => undefined) },
  { id: "desktop/player-speed", group: "Trình phát", title: "Tốc độ đọc", route: "/", act: () => click(/^Tốc độ đọc/).then(() => undefined) },
  { id: "desktop/player-full-speed", group: "Trình phát", title: "Tốc độ ở màn nghe", route: "/", act: async () => {
    await playerOpen(); await click(/^Tốc độ đọc/, document.querySelector('.now-playing')!);
  } },
  { id: "desktop/player-full-sleep", group: "Trình phát", title: "Hẹn giờ ở màn nghe", route: "/", act: async () => {
    await playerOpen(); await click(/^Hẹn giờ tắt/, document.querySelector('.now-playing')!);
  } },
  { id: "desktop/reader", group: "Đọc theo", title: "Đọc theo chương đang nghe", route: "/book/suong-mu-2/read/4" },
  { id: "desktop/reader-text", group: "Đọc theo", title: "Chế độ đọc sách chữ", route: "/book/gac-xep/read/2" },
  { id: "desktop/add-book-1", group: "Thêm sách", title: "Thêm sách · bước 1: chọn file", route: "/", act: () => click("Thêm sách").then(() => undefined) },
  { id: "desktop/add-book-2", group: "Thêm sách", title: "Thêm sách · bước 2: xem trước", route: "/", act: async () => {
    await click("Thêm sách");
    await type("Đường dẫn file hay thư mục", "D:/Truyện/Tiệm sách trên gác xép.epub");
    await click("Mở");
  } },
  { id: "desktop/add-book-3", group: "Thêm sách", title: "Thêm sách · bước 3: đã thêm (toast)", route: "/", act: async () => {
    await click("Thêm sách");
    await type("Đường dẫn file hay thư mục", "D:/Truyện/Tiệm sách trên gác xép.epub");
    await click("Mở");
    await click("Thêm vào thư viện");
  } },
  { id: "desktop/settings", group: "Cài đặt", title: "Cài đặt (gốc)", route: "/settings" },
  ...(["voice", "listen", "sleep", "look", "devices", "studio", "advanced"] as const).map((group): Omit<Entry, "platform"> => ({
    id: `desktop/settings-${group}`,
    group: "Cài đặt",
    title: `Cài đặt › ${SETTINGS_LABELS[group]}`,
    route: `/settings/${group}`,
    scenario: { installedStudio: true },
  })),
  { id: "desktop/studio-projects", group: "Studio", title: "Danh sách dự án", route: "/studio" },
  { id: "desktop/studio-projects-empty", group: "Studio", title: "Chưa có dự án", route: "/studio", scenario: { projects: "empty", library: "empty" } },
  { id: "desktop/studio-projects-loading", group: "Studio", title: "Đang tải dự án", route: "/studio", scenario: { projects: "loading" } },
  { id: "desktop/studio-project", group: "Studio", title: "Dự án đang thu âm", route: "/studio/dong-ho-cat" },
  { id: "desktop/studio-project-battery", group: "Studio", title: "Dự án tạm dừng vì chạy pin", route: "/studio/vi-sao-lac" },
  { id: "desktop/studio-project-analysis", group: "Studio", title: "Dự án đang phân tích", route: "/studio/thu-mua-dong" },
  { id: "desktop/studio-project-done", group: "Studio", title: "Dự án đã xong", route: "/studio/suong-mu-2" },
  { id: "desktop/studio-cast", group: "Studio", title: "Nhân vật và giọng", route: "/studio/dong-ho-cat?tab=cast" },
  { id: "desktop/studio-voice-picker", group: "Studio", title: "Chọn giọng cho nhân vật", route: "/studio/dong-ho-cat?tab=cast", act: () => click(/^Đổi giọng|^Chọn giọng/).then(() => undefined) },
  { id: "desktop/studio-work", group: "Studio", title: "Việc cần duyệt", route: "/studio/dong-ho-cat?tab=work" },
  { id: "desktop/studio-review", group: "Studio", title: "Cần nghe lại", route: "/studio/dong-ho-cat?tab=review" },
  { id: "desktop/studio-precast", group: "Studio", title: "Duyệt trước khi thu", route: "/studio/dong-ho-cat?tab=precast" },
  { id: "desktop/studio-script", group: "Studio", title: "Kịch bản chương", route: "/studio/dong-ho-cat?tab=script" },
  { id: "desktop/studio-music", group: "Studio", title: "Nhạc nền", route: "/studio/dong-ho-cat?tab=music" },
  { id: "desktop/studio-activity", group: "Studio", title: "Diễn biến", route: "/studio/dong-ho-cat?tab=activity" },
  { id: "desktop/studio-new", group: "Studio", title: "Tạo sách nói", route: "/studio/new" },
];


export const ENTRIES: Entry[] = [
  ...PHONE.map((item) => ({ ...item, platform: "phone" as const })),
  ...DESKTOP.map((item) => ({ ...item, platform: "desktop" as const })),
  ...(["phone", "desktop"] as const).flatMap(platform => (["skeleton", "empty", "error", "offline"] as const).map((showcase): Entry => ({
    id: `${platform}/state-${showcase}`, platform, group: "Trạng thái", title: ({ skeleton: "Khung chờ", empty: "Chưa có nội dung", error: "Lỗi tại chỗ", offline: "Mất mạng" })[showcase], route: "/", showcase,
  }))),
  { id: "desktop/sidebar-running", platform: "desktop", group: "Thanh bên", title: "Dự án chạy và chờ", route: "/studio", scenario: { queued: true } },
  { id: "desktop/offline-library", platform: "desktop", group: "Trạng thái", title: "Mất mạng, giữ thư viện", route: "/", act: async () => { window.dispatchEvent(new Event("offline")); } },
  { id: "phone/offline-library", platform: "phone", group: "Trạng thái", title: "Mất mạng, giữ thư viện", route: "/", act: async () => { window.dispatchEvent(new Event("offline")); } },
  ...(["loading", "error"] as const).flatMap(state => ([
    ["work", "Việc cần duyệt", "/studio/dong-ho-cat?tab=work", "/api/books/dong-ho-cat/work"],
    ["review", "Câu cần nghe", "/studio/dong-ho-cat?tab=review", "/api/books/dong-ho-cat/review"],
    ["precast", "Lượt duyệt", "/studio/dong-ho-cat?tab=precast", "/api/books/dong-ho-cat/precast"],
    ["script", "Kịch bản", "/studio/dong-ho-cat?tab=script", "/api/books/dong-ho-cat/casting"],
    ["music", "Nhạc nền", "/studio/dong-ho-cat?tab=music", "/api/books/dong-ho-cat/music"],
    ["devices", "Thiết bị", "/settings/devices", "/api/computers"],
    ["voice", "Giọng đọc", "/settings/voice", "/api/readaloud/voices"],
    ["app", "Mở ABook", "/", "/api/app"],
  ] as const).map(([id, title, route, path]): Entry => ({ id: `desktop/${id}-${state}`, platform: "desktop", group: "Trạng thái", title: `${title} · ${state === "loading" ? "đang tải" : "lỗi"}`, route, scenario: { requests: { [path]: state } } }))),
];

export function entry(id: string): Entry | undefined {
  return ENTRIES.find((item) => item.id === id);
}
