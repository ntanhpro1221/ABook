import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ tree: null as unknown, store: new Map<string, string>(), failWrites: false, error: vi.fn(), configure: vi.fn() }));
vi.mock("./plugins", () => ({ EbookPlayer: { configure: h.configure, listenPrefs: vi.fn() }, EbookLibrary: { systemBars: vi.fn() }, ReadAloud: {} }));
vi.mock("sonner", () => ({ toast: { error: h.error, success: vi.fn() } }));
import { SAVE_FAILED, SettingsScreen } from "./SettingsScreen";

// Màn Cài đặt của điện thoại (soát a100 V2, T2, T3): dựng bằng react-dom/server, lấy cây phần tử để gọi thẳng trình xử lý của công tắc.
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
const KEY = "abook-player-settings";

beforeEach(() => {
  h.store.clear();
  h.failWrites = false;
  h.error.mockReset();
  h.configure.mockReset().mockResolvedValue({});
  Object.assign(globalThis, {
    localStorage: {
      getItem: (key: string) => h.store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        if (h.failWrites) throw new Error("QuotaExceededError");
        h.store.set(key, value);
      },
    },
    window: Object.assign(new EventTarget(), {
      location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
      matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
    }),
  });
});

const rewindSwitch = (tree: unknown) => walk(tree, (node) => node.props?.["aria-label"] === "Tự lùi khi nghe lại")[0];

describe("SettingsScreen (điện thoại)", () => {
  it("lịch đêm hỏng trong kho không làm màn Cài đặt ném lỗi: về không có lịch", () => {
    h.store.set(KEY, JSON.stringify({ sleepSchedule: { from: { bad: 1 }, to: "06:00", minutes: 30 } }));
    expect(() => mount()).not.toThrow();
    const html = renderToString(<QueryClientProvider client={new QueryClient()}><SettingsScreen /></QueryClientProvider>);
    expect(html).not.toContain('aria-label="Số phút hẹn"');
  });

  it("ba ô chọn lịch đêm cao tối thiểu 48 dp", () => {
    h.store.set(KEY, JSON.stringify({ sleepSchedule: { from: "22:00", to: "06:00", minutes: 30 } }));
    const html = renderToString(<QueryClientProvider client={new QueryClient()}><SettingsScreen /></QueryClientProvider>);
    const selects = [...html.matchAll(/<select[^>]*>/g)].map((match) => match[0]);
    expect(selects).toHaveLength(3);
    for (const select of selects) expect(select).toContain("min-h-[48px]");
  });

  it("đổi tuỳ chọn thì lưu và không báo lỗi", () => {
    const toggle = rewindSwitch(mount());
    (toggle.props!.onCheckedChange as (value: boolean) => void)(false);
    expect(JSON.parse(h.store.get(KEY)!).autoRewind).toBe(false);
    expect(h.error).not.toHaveBeenCalled();
  });

  it("bộ nhớ WebView không ghi được thì báo bạn bằng tiếng Việt, và lõi nghe vẫn nhận giá trị mới", () => {
    h.failWrites = true;
    const toggle = rewindSwitch(mount());
    (toggle.props!.onCheckedChange as (value: boolean) => void)(false);
    expect(h.error).toHaveBeenCalledWith(SAVE_FAILED, expect.anything());
    expect(SAVE_FAILED).toContain("bạn");
    expect(h.configure).toHaveBeenLastCalledWith(expect.objectContaining({ autoRewind: false }));
  });
});
