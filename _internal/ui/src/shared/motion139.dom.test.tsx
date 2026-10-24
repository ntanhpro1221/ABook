// @vitest-environment happy-dom
// a139: bìa, tab và dòng cài đặt dùng chung không đổi cứng - mọi thay đổi nhìn thấy đều mờ chéo / hiện dần.
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { BookCover } from "./BookCover";
import { coverStyle } from "./cover";
import { SettingsList, SettingsRow } from "./SettingsNav";
import { Tabs, TabsContent, TabsList, TabsPanels, TabsTrigger, TooltipProvider } from "./ui";

let root: Root, host: HTMLDivElement;
let animate: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  animate = vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });
const render = async (node: ReactNode) => { await act(() => root.render(<MemoryRouter><TooltipProvider>{node}</TooltipProvider></MemoryRouter>)); };
const snapshots = () => [...document.querySelectorAll<HTMLElement>(".motion-snapshot")];
const animated = (match: (element: HTMLElement) => boolean) => (animate.mock.contexts as HTMLElement[]).filter(match);

it("C7 bìa: đổi cuốn và ảnh lỗi rơi về bìa vẽ đều mờ chéo trên cùng một khung", async () => {
  const cover = (title: string, url?: string) => <BookCover title={title} image={url ? { url, width: 100, height: 100 } : undefined} size="sm" className="size-12" />;
  await render(cover("Sách A"));
  const frame = host.firstElementChild as HTMLElement;
  await render(cover("Sách B"));
  expect(host.firstElementChild).toBe(frame);
  expect(animated((element) => element === frame)).toHaveLength(1);
  expect(snapshots().some((image) => image.style.background.includes(coverStyle("Sách A").from) || image.getAttribute("style")?.includes(coverStyle("Sách A").from))).toBe(true);
  // Bìa vẽ -> ảnh thật -> ảnh lỗi: vẫn một khung (không thay hai cây), mỗi lần đổi có ảnh cũ inert.
  await render(cover("Sách B", "/b.jpg"));
  expect(host.firstElementChild).toBe(frame);
  expect(host.querySelector("img")).not.toBeNull();
  animate.mockClear();
  await act(() => { host.querySelector("img")!.dispatchEvent(new Event("error")); });
  expect(host.firstElementChild).toBe(frame);
  expect(host.querySelector("img")).toBeNull();
  expect(animated((element) => element === frame)).toHaveLength(1);
  expect(snapshots().some((image) => image.querySelector("img"))).toBe(true);
});

it("C7 ảnh bìa lười: ẩn tới khi tải xong rồi hiện dần; ảnh đã có sẵn hiện ngay", async () => {
  await render(<BookCover title="Sách" image={{ url: "/a.jpg", width: 100, height: 150 }} />);
  const images = [...host.querySelectorAll("img")];
  expect(images).toHaveLength(2);
  for (const image of images) {
    expect(image.className).toContain("transition-opacity");
    expect(image.className).toContain("opacity-0");
  }
  await act(() => { images[1].dispatchEvent(new Event("load")); });
  expect(images[1].className).toContain("opacity-100");
  expect(images[0].className).toContain("opacity-60");
  await act(() => root.unmount()); root = createRoot(host);
  const complete = vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(true);
  const natural = vi.spyOn(HTMLImageElement.prototype, "naturalWidth", "get").mockReturnValue(100);
  await render(<BookCover title="Sách" image={{ url: "/cached.jpg", width: 100, height: 100 }} />);
  expect(host.querySelector("img")!.className).toContain("opacity-100");
  complete.mockRestore(); natural.mockRestore();
});

it("V10 tab: đổi tab giữ bảng cũ trong ảnh inert và chuyển chiều cao, không gỡ ngay", async () => {
  const tabs = (value: string) => (
    <Tabs value={value}>
      <TabsList label="Mục"><TabsTrigger value="a">A</TabsTrigger><TabsTrigger value="b">B</TabsTrigger></TabsList>
      <TabsPanels value={value}>
        <TabsContent value="a"><p>Bảng A</p></TabsContent>
        <TabsContent value="b"><p>Bảng B dài hơn</p></TabsContent>
      </TabsPanels>
    </Tabs>
  );
  await render(tabs("a"));
  await render(tabs("b"));
  expect(host.textContent).toContain("Bảng B dài hơn");
  const old = snapshots().find((image) => image.textContent?.includes("Bảng A"));
  expect(old?.hasAttribute("inert")).toBe(true);
  const panels = host.querySelector<HTMLElement>("[role=tabpanel]")!.parentElement!;
  expect(panels.hasAttribute("data-motion-region")).toBe(true);
  expect(animated((element) => element === panels)).toHaveLength(1);
});

it("V11 dòng cài đặt: tên / mô tả đổi thì mờ chéo; số chạy không chụp lại", async () => {
  const row = (label: string, hint: string) => <SettingsRow label={label} hint={hint}><button type="button">Bật</button></SettingsRow>;
  await render(row("Thông báo", "Đang tắt"));
  await render(row("Thông báo", "Đang bật"));
  expect(snapshots().find((image) => image.textContent?.includes("Đang tắt"))?.hasAttribute("inert")).toBe(true);
  expect(host.querySelector("button")!.closest("[data-motion-region]")).toBeNull(); // điều khiển không bị chụp / mờ theo
  animate.mockClear();
  await render(row("Thông báo", "Còn 3 phút"));
  animate.mockClear();
  await render(row("Thông báo", "Còn 2 phút"));
  expect(animate).not.toHaveBeenCalled();
});

it("V12 danh sách nhóm: dòng giá trị hiện tại đổi / mới có thì mờ chéo", async () => {
  await render(<SettingsList rows={[{ id: "voice", summary: "Giọng A" }, { id: "advanced" }]} />);
  await render(<SettingsList rows={[{ id: "voice", summary: "Giọng B" }, { id: "advanced", summary: "Phiên bản 1.0" }]} />);
  expect(snapshots().find((image) => image.textContent === "Giọng A")?.hasAttribute("inert")).toBe(true);
  expect(animated((element) => element.textContent === "Phiên bản 1.0")).toHaveLength(1);
});
