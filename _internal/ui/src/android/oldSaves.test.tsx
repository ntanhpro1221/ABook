import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({
  exportOldSave: vi.fn(),
  deleteOldSave: vi.fn(),
  toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));
vi.mock("./plugins", () => ({
  EbookPlayer: { configure: vi.fn(), listenPrefs: vi.fn() },
  EbookLibrary: { systemBars: vi.fn(), exportOldSave: h.exportOldSave, deleteOldSave: h.deleteOldSave, listOldSaves: vi.fn() },
  ReadAloud: {},
}));
vi.mock("sonner", () => ({ toast: h.toast }));
import { deleteOldSave, exportOldSave, OldSaveDeleteDialog } from "./OldSaves";
import { newOldSaves, oldSaveNotice, oldSaveTitle, OLD_SAVES_KEY, type OldSave } from "./oldSaveList";
import { SettingsScreen } from "./SettingsScreen";
import { SettingsAt } from "@/shared/settingsAt";

// Màn "Bản lưu cũ" (soát a106 G3): hiện / ẩn mục trong Cài đặt, xác nhận trước khi xoá, câu báo một lần ở Thư viện.

const file = (name: string, size = 2048): OldSave => ({ name, size, modified: 1_700_000_000 });
const A = file("Truyện dài 20260101-101010.abook");
const B = file("Sách khác 20260102-111111.abookproj", 4096);

type Node = { type?: unknown; props?: Record<string, unknown> };
function walk(node: unknown, found: (node: Node) => boolean): Node[] {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap((child) => walk(child, found));
  const element = node as Node;
  return [...(found(element) ? [element] : []), ...walk(element.props?.children, found)];
}

function settingsHtml(files: OldSave[] | undefined): string {
  const client = new QueryClient();
  if (files) client.setQueryData(OLD_SAVES_KEY, files);
  return renderToString(
    <QueryClientProvider client={client}>
      <SettingsAt group="advanced" screen={<SettingsScreen />} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  h.exportOldSave.mockReset();
  h.deleteOldSave.mockReset();
  h.toast.mockReset();
  h.toast.error.mockReset();
  h.toast.success.mockReset();
  Object.assign(globalThis, {
    localStorage: { getItem: () => null, setItem: () => undefined },
    window: Object.assign(new EventTarget(), {
      location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
      matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    }),
  });
});

describe("Bản lưu cũ trong Cài đặt", () => {
  it("không có file (hay chưa hỏi xong) thì không hiện mục", () => {
    expect(settingsHtml(undefined)).not.toContain("Bản lưu cũ");
    expect(settingsHtml([])).not.toContain("Bản lưu cũ");
  });

  it("có file thì hiện mục kèm số lượng, tên sách, cỡ và hai nút", () => {
    const html = settingsHtml([A, B]);
    expect(html).toContain("Bản lưu cũ (2)");
    expect(html).toContain("Truyện dài");
    expect(html).toContain("Sách khác");
    expect(html).not.toContain("20260101-101010");
    expect(html).toContain("Lưu ra…");
    expect(html).toContain("Xoá…");
  });
});

describe("xác nhận xoá", () => {
  const dialog = (target: OldSave | null, onConfirm = vi.fn(), onCancel = vi.fn()) =>
    OldSaveDeleteDialog({ file: target, busy: false, onConfirm, onCancel }) as unknown as Node;

  it("hộp nói rõ không lấy lại được và chỉ xoá khi bấm Xoá", () => {
    const onConfirm = vi.fn();
    const tree = dialog(A, onConfirm);
    expect(tree.props?.open).toBe(true);
    expect(String(tree.props?.description)).toContain("không lấy lại được");
    expect(String(tree.props?.description)).toContain("Truyện dài");
    expect(onConfirm).not.toHaveBeenCalled();
    const buttons = walk(tree, (node) => typeof node.props?.onClick === "function");
    expect(buttons).toHaveLength(2);
    (buttons[1].props!.onClick as () => void)();
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("Giữ lại thì không xoá gì và hộp đóng", () => {
    const onCancel = vi.fn();
    const tree = dialog(A, vi.fn(), onCancel);
    (walk(tree, (node) => typeof node.props?.onClick === "function")[0].props!.onClick as () => void)();
    expect(onCancel).toHaveBeenCalledOnce();
    expect(h.deleteOldSave).not.toHaveBeenCalled();
    expect(dialog(null).props?.open).toBe(false);
  });

  it("xoá gọi đúng file một lần; lỗi thì báo và không coi là đã xoá", async () => {
    h.deleteOldSave.mockResolvedValue({ deleted: true });
    expect(await deleteOldSave(A)).toBe(true);
    expect(h.deleteOldSave).toHaveBeenCalledWith({ name: A.name });
    h.deleteOldSave.mockRejectedValue(new Error("Không thấy bản lưu cũ này"));
    expect(await deleteOldSave(A)).toBe(false);
    expect(h.toast.error).toHaveBeenCalledWith("Chưa xoá được", { description: "Không thấy bản lưu cũ này" });
  });
});

describe("Lưu ra…", () => {
  it("gọi hộp lưu của hệ thống; bỏ qua hộp thì im lặng", async () => {
    h.exportOldSave.mockResolvedValueOnce({ saved: true }).mockResolvedValueOnce({ saved: false });
    expect(await exportOldSave(A)).toBe(true);
    expect(h.exportOldSave).toHaveBeenCalledWith({ name: A.name });
    expect(await exportOldSave(A)).toBe(false);
    expect(h.toast.success).toHaveBeenCalledTimes(1);
    expect(h.toast.error).not.toHaveBeenCalled();
  });
});

describe("báo một lần ở Thư viện", () => {
  it("chỉ báo file chưa từng báo, nói tên sách", () => {
    expect(newOldSaves([A, B], [A.name])).toEqual([B]);
    expect(newOldSaves([A], [A.name])).toEqual([]);
    expect(oldSaveNotice([A])).toBe("Có bản lưu cũ của “Truyện dài” chưa trả lại được - mở trong Cài đặt");
    expect(oldSaveNotice([A, B])).toBe("Có 2 bản lưu cũ chưa trả lại được - mở trong Cài đặt");
  });

  it("tên sách cắt đuôi dấu giờ và đuôi file", () => {
    expect(oldSaveTitle("Truyện dài 20260101-101010.abook")).toBe("Truyện dài");
    expect(oldSaveTitle("Dự án 20260101-101010.abookproj")).toBe("Dự án");
    expect(oldSaveTitle("tên lạ.abook")).toBe("tên lạ");
  });
});
