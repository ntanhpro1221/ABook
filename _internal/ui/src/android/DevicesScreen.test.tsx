import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";

// Mục "Thiết bị": hàng cập nhật tên (soát a97 V1) và dung lượng có hàng xoá cho phần tải dở (V6). Plugin native và danh sách thư viện là bản giả.
const hooks = vi.hoisted(() => ({ books: [] as unknown[], progress: {} as Record<string, unknown> }));
vi.mock("./plugins", () => ({ EbookLibrary: {}, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("@/listen/source", async (original) => ({ ...(await original<object>()), useListenLibrary: () => ({ data: hooks.books }) }));
vi.mock("./downloads", () => ({ useDownloadProgress: () => hooks.progress }));

import { RemoteRow, StoragePanel } from "./DevicesScreen";

const downloaded = { id: "book", title: "Tên", author: "Tác giả", chaptersAvailable: 1, chaptersTotal: 1, downloaded: true, localChapters: 1,
  duration: 100, audioVersion: "same", localAudioVersion: "same", metaVersion: "m1", localMetaVersion: "m1" };

beforeEach(() => {
  hooks.books = [];
  hooks.progress = {};
});

it("đổi riêng tên / tác giả ở máy tính: bản đã tải có nút Cập nhật tên, khớp dấu thì chỉ ghi Đã tải", () => {
  const same = renderToStaticMarkup(<RemoteRow book={downloaded as never} onDownload={vi.fn()} />);
  expect(same).toContain("Đã tải");
  expect(same).not.toContain("<button");
  const changed = renderToStaticMarkup(<RemoteRow book={{ ...downloaded, title: "Tên mới", metaVersion: "m2" } as never} onDownload={vi.fn()} />);
  expect(changed).toContain("Cập nhật tên");
  expect(changed).not.toContain("Đã tải");
  // Máy tính cũ không gửi dấu: không bao giờ có gì mới.
  const legacy = renderToStaticMarkup(<RemoteRow book={{ ...downloaded, metaVersion: undefined, localMetaVersion: "" } as never} onDownload={vi.fn()} />);
  expect(legacy).toContain("Đã tải");
});

it("phần tải dở (không có gói sách) và gói chỉ nghe thẳng đều có hàng và nút xoá", () => {
  const storage = { bytes: 700_000_000, free: 1_000_000_000, books: [{ id: "partial", bytes: 600_000_000 }, { id: "streamonly", bytes: 100_000_000, title: "Chỉ nghe thẳng" }] };
  hooks.books = [{ id: "streamonly", title: "Chỉ nghe thẳng", remote: true }];
  const html = renderToStaticMarkup(<StoragePanel storage={storage} names={new Map([["partial", "Sách đang tải"]])} />);
  expect(html).toContain("Sách trên máy:");
  expect(html).toContain("Sách đang tải");
  expect(html).toContain("Xoá phần đã tải của Sách đang tải");
  expect(html).toContain("Xoá phần đã tải của Chỉ nghe thẳng");
  expect(html).not.toContain(`disabled=""`);
});

it("cuốn đã tải xong vẫn xoá cả cuốn; cuốn đang có lượt tải chạy thì nút xoá tắt", () => {
  hooks.books = [{ id: "done", title: "Đã tải", remote: false }];
  hooks.progress = { partial: { bookId: "partial", done: 1, total: 10, files: 1, filesTotal: 3 } };
  const storage = { bytes: 5, free: 5, books: [{ id: "done", bytes: 3 }, { id: "partial", bytes: 2 }] };
  const html = renderToStaticMarkup(<StoragePanel storage={storage} />);
  expect(html).toContain("Xoá Đã tải khỏi điện thoại");
  const partial = html.match(/<button[^>]*Xoá phần đã tải của Sách tải dở[^>]*>/)![0];
  expect(partial).toContain(`disabled=""`);
  expect(html.match(/<button[^>]*Xoá Đã tải khỏi điện thoại[^>]*>/)![0]).not.toContain(`disabled=""`);
});
