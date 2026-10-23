import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ api: vi.fn(), success: vi.fn(), error: vi.fn(), tree: null as unknown }));
vi.mock("@/studio/api", () => ({ api: h.api }));
vi.mock("@/studio/data", () => ({ pickFolder: vi.fn() }));
vi.mock("sonner", () => ({ toast: { success: h.success, error: h.error } }));
import { LibraryMoveRecovery } from "./LibraryMoveRecovery";

type Node = { props?: Record<string, unknown> };
function walk(node: unknown): Node[] {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap(walk);
  const element = node as Node;
  return [element, ...walk(element.props?.children)];
}
function mount() {
  function Probe() {
    h.tree = LibraryMoveRecovery({ recovery: { message: "Bạn hãy xử lý lần chuyển trước", currentRoot: "D:/Books" } });
    return null;
  }
  renderToString(<QueryClientProvider client={new QueryClient()}><Probe /></QueryClientProvider>);
  return walk(h.tree);
}
const flush = async () => { for (let i = 0; i < 15; i++) await Promise.resolve(); };
beforeEach(() => { vi.clearAllMocks(); h.api.mockResolvedValue({}); });

it.each([
  ["Hoàn tất chuyển thư viện", "finish"], ["Quay lui", "rollback"], ["Bỏ qua lần chuyển này", "ignore"],
])("%s gửi lựa chọn rõ ràng và cả hai đường dẫn", async (label, action) => {
  const button = mount().find((n) => n.props?.children === label)!;
  (button.props!.onClick as () => void)();
  expect(h.success).not.toHaveBeenCalled();
  await flush();
  expect(h.api).toHaveBeenCalledWith("/api/library-move/recovery", { method: "POST", body: { action, oldRoot: "D:/Books", newRoot: "D:/Books" } });
  expect(h.success).toHaveBeenCalledOnce();
});

it("lỗi giữ nhật ký hoặc thư mục mất: báo lỗi, không báo thành công", async () => {
  h.api.mockRejectedValue(new Error("Bạn hãy chọn thư mục còn tồn tại"));
  const button = mount().find((n) => n.props?.children === "Quay lui")!;
  (button.props!.onClick as () => void)();
  await flush();
  expect(h.success).not.toHaveBeenCalled();
  expect(h.error).toHaveBeenCalledWith("Bạn hãy chọn thư mục còn tồn tại");
});
