// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/shared/ui";

const h = vi.hoisted(() => ({ discover: vi.fn(), pair: vi.fn(), release: vi.fn(), bluetooth: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: {
  connection: async () => ({ paired: false }), discover: h.discover, pair: h.pair,
  bluetoothPermission: async () => ({ state: "granted" }), bluetoothDevices: h.bluetooth,
}, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("./UpdateNotice", () => ({ openRelease: h.release }));
import { ComputerIntro, PairPanel, DESKTOP_RELEASES } from "./DevicesScreen";

let root: Root, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  h.discover.mockReset().mockResolvedValue({ computers: [{ host: "192.168.1.20", port: 47630, name: "Máy tính" }] });
  h.pair.mockReset().mockResolvedValue({ name: "Máy tính" });
  h.bluetooth.mockReset().mockResolvedValue({ devices: [] });
  h.release.mockReset();
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const wait = () => act(() => new Promise(resolve => setTimeout(resolve, 50)));
const button = (text: string) => Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(b => b.textContent?.includes(text))!;
const input = async (element: HTMLInputElement, value: string) => {
  await act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  });
};

it("hàng tải có nhãn ngắn và chép đúng URL, mở đúng trang tải", async () => {
  const copy = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: copy } });
  await act(() => root.render(<TooltipProvider><ComputerIntro /></TooltipProvider>));
  expect(document.body.textContent).not.toContain("github.com");
  const download = document.querySelector<HTMLAnchorElement>("a")!;
  expect(download.href).toBe(DESKTOP_RELEASES);
  await act(() => download.click());
  expect(h.release).toHaveBeenCalledWith(DESKTOP_RELEASES);
  await act(() => document.querySelector<HTMLButtonElement>('[aria-label="Chép địa chỉ"]')!.click());
  expect(copy).toHaveBeenCalledWith(DESKTOP_RELEASES);
});

it("hàng máy tìm thấy giữ quét lại, Bluetooth, nhập tay và gửi mã ghép", async () => {
  await act(() => root.render(<QueryClientProvider client={client}><PairPanel /></QueryClientProvider>));
  await wait();
  expect(h.discover).toHaveBeenCalledOnce();
  await act(() => button("Tìm lại").click()); await wait();
  expect(h.discover).toHaveBeenCalledTimes(2);
  await act(() => button("Dùng Bluetooth").click()); await wait();
  expect(h.bluetooth).toHaveBeenCalledOnce();
  await act(() => button("Nhập địa chỉ").click()); await wait();
  const address = document.querySelector<HTMLInputElement>('input[inputmode="url"]')!;
  expect(address.classList.contains("device-input")).toBe(true);
  await input(address, "192.168.1.30:47631");
  await input(document.querySelector<HTMLInputElement>('input[inputmode="numeric"]')!, "123456");
  expect(button("Kết nối").disabled).toBe(false);
  await act(() => button("Kết nối").click()); await wait();
  expect(h.pair).toHaveBeenCalledWith({ host: "192.168.1.30", port: 47631, code: "123456" });
});
