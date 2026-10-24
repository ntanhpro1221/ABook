// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { onlineManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";
import { MemoryRouter } from "react-router";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { MOTION } from "./motion";
import { Button, ContentSkeleton, EmptyState, InlineError, OfflineStrip, TooltipProvider } from "./ui";

const h = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("@/studio/api", async original => ({ ...await original<typeof import("@/studio/api")>(), api: h.api }));
vi.mock("@/studio/data", () => ({ useAppInfo: () => ({ data: { dialogs: true } }), pickFolder: vi.fn() }));
import { MusicSection } from "@/listen/EditBook";
import { SwapTrack } from "@/listen/MyMusic";
import { OtherComputers } from "@/desktop/OtherComputers";
import { PhoneSync } from "@/desktop/PhoneSync";

let root: Root, host: HTMLDivElement, client: QueryClient;
const draw = (node: ReactNode) => act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter></QueryClientProvider>));
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); h.api.mockReset(); onlineManager.setOnline(true);
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 300, bottom: 100, width: 300, height: 100, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); host.remove(); vi.clearAllTimers(); vi.restoreAllMocks(); vi.useRealTimers(); });

it.each(["rows", "cards", "covers"] as const)("skeleton %s có nhãn tải và khung đúng hình, không spinner", async shape => {
  await draw(<ContentSkeleton shape={shape} count={3} label="Đang tải sách" />);
  expect(host.querySelector('[role="status"]')?.getAttribute("aria-label")).toBe("Đang tải sách");
  expect(host.querySelectorAll('.motion-skeleton[aria-hidden="true"]')).toHaveLength(9);
  expect(host.querySelector(".animate-spin")).toBeNull();
  if (shape === "covers") expect(host.querySelectorAll(".aspect-\\[2\\/3\\]")).toHaveLength(3);
});

it("khung chờ nhịp 1,6 giây và giữ quy tắc giảm chuyển động", () => {
  const css = readFileSync(`${cwd()}/src/styles.css`, "utf8");
  expect(css).toContain("state-skeleton-pulse 1.6s");
  expect(css).toContain("50% { opacity: .6; }");
  expect(css).toContain(".motion-skeleton { animation: fade-in var(--motion-fast) linear backwards !important; }");
});

it("trạng thái rỗng có một câu và một nút tạo nội dung", async () => {
  const create = vi.fn();
  const { BookOpen } = await import("lucide-react");
  await draw(<EmptyState icon={BookOpen} title="Thêm sách của bạn" action={<Button onClick={create}>Thêm sách</Button>} />);
  expect(host.querySelectorAll("button")).toHaveLength(1);
  await act(() => host.querySelector<HTMLButtonElement>("button")!.click());
  expect(create).toHaveBeenCalledTimes(1);
});

it("lỗi tại chỗ có hướng sửa và Thử lại thực hiện lệnh", async () => {
  const retry = vi.fn();
  await draw(<InlineError message="Bạn hãy kiểm tra kết nối rồi thử lại." onRetry={retry} />);
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("kiểm tra kết nối");
  expect(host.querySelector("button")?.textContent).toBe("Thử lại");
  expect(host.querySelector('[role="dialog"]')).toBeNull();
  await act(() => host.querySelector<HTMLButtonElement>("button")!.click()); expect(retry).toHaveBeenCalledTimes(1);
});

it("mất mạng vào/ra bằng presence; nội dung và tiêu điểm vẫn dùng được", async () => {
  const play = vi.fn();
  await draw(<><OfflineStrip /><Button onClick={play}>Nghe tiếp</Button></>);
  const button = host.querySelector<HTMLButtonElement>("button")!; button.focus();
  await act(() => window.dispatchEvent(new Event("offline")));
  expect(host.querySelector('.motion-panel[data-state="open"] [role="status"]')?.textContent).toContain("Mất mạng");
  await act(() => vi.advanceTimersByTime(MOTION.medium + 300));
  expect(host.querySelector("button")).toBe(button); expect(document.activeElement).toBe(button);
  await act(() => button.click()); expect(play).toHaveBeenCalledTimes(1);
  await act(() => window.dispatchEvent(new Event("online")));
  const closing = host.querySelector<HTMLElement>('.motion-panel[data-state="closed"]');
  expect(closing?.inert).toBe(true); expect(closing?.getAttribute("aria-hidden")).toBe("true");
  await act(() => vi.advanceTimersByTime(MOTION.mediumOut + 300));
  expect(host.querySelector('[role="status"]')).toBeNull(); expect(host.querySelector("button")).toBe(button);
});

const screens: [string, () => ReactNode][] = [
  ["nhạc của sách", () => <MusicSection book={{ id: "a" } as ListenBook} />],
  ["đổi bài", () => <SwapTrack bookId="a" cueKey="1" busy={false} choosing={null} onChoose={() => {}} />],
  ["thiết bị", () => <OtherComputers />],
  ["kết nối", () => <PhoneSync />],
];
it.each(screens)("%s: khi tải hiện skeleton thay vòng xoay", async (_name, screen) => {
  h.api.mockImplementation(() => new Promise(() => {}));
  await draw(screen());
  expect(host.querySelector('[role="status"] .motion-skeleton')).not.toBeNull();
  expect(host.querySelector(".animate-spin")).toBeNull();
});
it.each(screens)("%s: lỗi có Thử lại gọi lại truy vấn", async (_name, screen) => {
  h.api.mockRejectedValue(new Error("Mất kết nối"));
  await draw(screen());
  await act(() => vi.advanceTimersByTime(20));
  const retry = host.querySelector<HTMLButtonElement>('[role="alert"] button');
  expect(retry?.textContent).toBe("Thử lại");
  const calls = h.api.mock.calls.length;
  await act(() => retry!.click());
  expect(h.api.mock.calls.length).toBeGreaterThan(calls);
});
