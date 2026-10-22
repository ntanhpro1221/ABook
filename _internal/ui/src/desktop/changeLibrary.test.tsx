import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({
  tree: null as unknown,
  prefs: { libraryRoot: "D:/Old", theme: "system" },
  update: vi.fn(),
  pick: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  mutation: null as null | { onError?: (error: Error) => void; onSuccess?: (data: unknown) => void },
}));
vi.mock("@/studio/data", async (original) => ({
  ...(await original<typeof import("@/studio/data")>()),
  usePreferences: () => ({ data: h.prefs, update: h.update }),
  pickFolder: () => h.pick(),
  useAppInfo: () => ({ data: { dialogs: true, remote: false } }),
  useVoices: () => ({ data: [] }),
}));
vi.mock("sonner", () => ({ toast: { success: h.success, error: h.error, warning: vi.fn() } }));
vi.mock("@/listen/VoiceSettings", () => ({ VoiceSettings: () => null }));
import { SettingsScreen } from "./SettingsScreen";

// Đổi thư mục thư viện (soát a100 V3): "Đã đổi thư mục" chỉ hiện khi máy chủ đã nhận; bị từ chối thì không có lời báo thành công.
type Node = { props?: Record<string, unknown> };
function walk(node: unknown, found: (node: Node) => boolean): Node[] {
  if (!node || typeof node !== "object") return [];
  if (Array.isArray(node)) return node.flatMap((child) => walk(child, found));
  const element = node as Node;
  return [...(found(element) ? [element] : []), ...walk(element.props?.children, found)];
}
function mount() {
  function Probe() {
    h.tree = SettingsScreen();
    return null;
  }
  renderToString(
    <QueryClientProvider client={new QueryClient()}>
      <Probe />
    </QueryClientProvider>,
  );
  return h.tree;
}
const flush = async () => {
  for (let i = 0; i < 10; i++) await Promise.resolve();
};

beforeEach(() => {
  vi.clearAllMocks();
  h.pick.mockResolvedValue("D:/Protected");
  Object.assign(globalThis, {
    window: Object.assign(new EventTarget(), {
      location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
      matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    }),
  });
});

describe("Đổi thư mục thư viện", () => {
  it("chưa báo thành công khi mới gửi; báo khi máy chủ nhận (onSuccess)", async () => {
    const button = walk(mount(), (node) => node.props?.children === "Đổi thư mục")[0];
    (button.props!.onClick as () => void)();
    await flush();
    expect(h.update).toHaveBeenCalledWith({ libraryRoot: "D:/Protected" }, expect.objectContaining({ onSuccess: expect.any(Function) }));
    expect(h.success).not.toHaveBeenCalled();
    (h.update.mock.calls[0][1] as { onSuccess: () => void }).onSuccess();
    expect(h.success).toHaveBeenCalledWith("Đã đổi thư mục thư viện");
  });

  it("máy chủ từ chối (không gọi onSuccess) thì không bao giờ có lời báo thành công", async () => {
    const button = walk(mount(), (node) => node.props?.children === "Đổi thư mục")[0];
    (button.props!.onClick as () => void)();
    await flush();
    expect(h.success).not.toHaveBeenCalled();
  });
});
