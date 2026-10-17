import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Ghi chú "cho ABook chạy nền" trong khung xuất (android/BackgroundNote.tsx). Plugin native và thông báo được thay bằng bản giả;
// phần Kotlin (LibraryPlugin.backgroundStatus) chỉ đọc PowerManager.isIgnoringBatteryOptimizations nên không có test JVM riêng.
const library = vi.hoisted(() => ({
  backgroundStatus: vi.fn(),
  openAppSettings: vi.fn(async () => undefined),
}));
const toasts = vi.hoisted(() => Object.assign(vi.fn(), { error: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("sonner", () => ({ toast: toasts }));

import { BackgroundNoteView, ExportProgressText, openBackgroundSettings, readBackground, watchBackground } from "./BackgroundNote";

/** Tìm phần tử có `onClick` trong cây (hàm thành phần không có hook thì gọi thẳng được). */
function findClick(node: ReactNode): (() => void) | undefined {
  if (!isValidElement(node)) return undefined;
  const element = node as ReactElement<{ onClick?: () => void; children?: ReactNode }>;
  if (element.props.onClick) return element.props.onClick;
  for (const child of [element.props.children].flat()) {
    const found = findClick(child as ReactNode);
    if (found) return found;
  }
  return undefined;
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("ghi chú cho ABook chạy nền", () => {
  beforeEach(() => vi.clearAllMocks());

  it("chưa cho phép: hiện ghi chú, nút, lời chỉ đường theo hãng", () => {
    const html = renderToString(<BackgroundNoteView status={{ manufacturer: "OPPO", backgroundAllowed: false }} />);
    expect(html).toContain("Xuất sách dài khi tắt màn hình có thể bị máy tạm dừng.");
    expect(html).toContain("Cho ABook chạy nền");
    expect(html).toContain("Cho phép hoạt động dưới nền");
  });

  it("nút mở trang cài đặt của ABook", () => {
    const click = findClick(BackgroundNoteView({ status: { manufacturer: "OPPO", backgroundAllowed: false } }));
    expect(click).toBeTypeOf("function");
    click!();
    expect(library.openAppSettings).toHaveBeenCalledTimes(1);
  });

  it("mở cài đặt lỗi thì báo bằng thông báo", async () => {
    library.openAppSettings.mockRejectedValueOnce(new Error("Không mở được cài đặt của ABook"));
    await openBackgroundSettings();
    expect(toasts.error).toHaveBeenCalledWith("Không mở được cài đặt của ABook");
  });

  it("đã cho phép hay không đọc được: không hiện gì", () => {
    expect(renderToString(<BackgroundNoteView status={{ manufacturer: "OPPO", backgroundAllowed: true }} />)).toBe("");
    expect(renderToString(<BackgroundNoteView status={undefined} />)).toBe("");
  });

  it("thông báo đang xuất vẫn là chữ tiến độ, chưa có ghi chú khi chưa đọc xong", () => {
    const html = renderToString(<ExportProgressText shown="Chương 2/5 · 30%" spoken="Đang xuất" />);
    expect(html).toContain("Chương 2/5 · 30%");
    expect(html).not.toContain("chạy nền");
  });

  it("readBackground: lỗi hay trả về lạ (máy tính, web) là không biết", async () => {
    library.backgroundStatus.mockResolvedValueOnce({ manufacturer: "OPPO", backgroundAllowed: false });
    expect(await readBackground()).toEqual({ manufacturer: "OPPO", backgroundAllowed: false });
    library.backgroundStatus.mockRejectedValueOnce(new Error("không có"));
    expect(await readBackground()).toBeUndefined();
    library.backgroundStatus.mockResolvedValueOnce({});
    expect(await readBackground()).toBeUndefined();
  });
});

describe("đọc lại khi app trở lại màn hình", () => {
  const original = (globalThis as { document?: unknown }).document;
  let doc: EventTarget & { visibilityState: string };
  beforeEach(() => {
    vi.clearAllMocks();
    doc = Object.assign(new EventTarget(), { visibilityState: "visible" });
    (globalThis as { document?: unknown }).document = doc;
  });
  afterEach(() => {
    (globalThis as { document?: unknown }).document = original;
  });

  it("đọc ngay, đọc lại mỗi lần hiện lại; bật xong thì thành đã cho phép", async () => {
    library.backgroundStatus
      .mockResolvedValueOnce({ manufacturer: "OPPO", backgroundAllowed: false })
      .mockResolvedValueOnce({ manufacturer: "OPPO", backgroundAllowed: true });
    const seen: unknown[] = [];
    const stop = watchBackground((status) => seen.push(status?.backgroundAllowed));
    await flush();
    expect(seen).toEqual([false]);
    doc.visibilityState = "hidden"; // ra ngoài app: không hỏi
    doc.dispatchEvent(new Event("visibilitychange"));
    await flush();
    expect(library.backgroundStatus).toHaveBeenCalledTimes(1);
    doc.visibilityState = "visible"; // quay lại sau khi bật trong Cài đặt
    doc.dispatchEvent(new Event("visibilitychange"));
    await flush();
    expect(seen).toEqual([false, true]);
    stop();
    doc.dispatchEvent(new Event("visibilitychange"));
    await flush();
    expect(library.backgroundStatus).toHaveBeenCalledTimes(2);
  });
});
