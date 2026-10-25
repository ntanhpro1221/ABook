// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { Toaster } from "sonner";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { toast } from "./toast";
import { Dialog, InlineError } from "./ui";
import { SectionHeading } from "./SectionHeading";
import { Fold } from "./Collapse";
import { SettingsBlock } from "./SettingsNav";
import { dismissTopLayer } from "@/android/backLayers";
import { installBackOrder } from "./backOrder";

let root: Root, stop: () => void;
const wait = () => act(() => new Promise(resolve => setTimeout(resolve, 40)));
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  stop = installBackOrder();
});
afterEach(async () => { stop(); await act(() => { toast.dismiss(); root.unmount(); }); document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const button = (text: string) => [...document.querySelectorAll<HTMLButtonElement>("button")].find(el => el.textContent === text)!;

it("tiêu đề đứng riêng, Fold và khối Settings cùng token; gập không đổi chữ / mất phần tử", async () => {
  await act(() => root.render(<><SectionHeading>Bộ nhớ</SectionHeading><Fold storageKey="c11.title" title="Edge">Danh sách</Fold><SettingsBlock title="Chẩn đoán" fold="c11.diagnostic">Lỗi</SettingsBlock></>));
  const titles = [...document.querySelectorAll('[data-section-title]')];
  expect(titles).toHaveLength(3);
  expect(titles.every(el => el.classList.contains('section-title'))).toBe(true);
  expect(document.querySelectorAll('[data-section-heading]')).toHaveLength(3);
  const fold = document.querySelector<HTMLButtonElement>('button[aria-controls]')!, body = document.getElementById(fold.getAttribute('aria-controls')!)!;
  await act(() => fold.click()); expect(body.dataset.state).toBe('open');
  await act(() => fold.click()); expect(body.dataset.state).toBe('closed'); expect(body.inert).toBe(true);
  expect(document.querySelectorAll('[data-section-title]')[1]).toBe(titles[1]);
});

it("lỗi cân dòng vẫn giữ hướng sửa và nút thử lại", async () => {
  const retry = vi.fn();
  await act(() => root.render(<InlineError message="Bạn hãy kiểm tra kết nối rồi thử lại." onRetry={retry} />));
  expect(document.querySelector('[role="alert"] p')?.classList.contains('text-balance')).toBe(true);
  await act(() => button('Thử lại').click()); expect(retry).toHaveBeenCalledOnce();
});

it("toast lỗi một dòng và một nút; chi tiết giữ nguyên lý do + hành động, không chồng dialog, Back đóng đúng thứ tự", async () => {
  const retry = vi.fn();
  function Example() { const [open, setOpen] = useState(true); return <><Dialog open={open} onOpenChange={setOpen} title="Sửa sách">Tên sách</Dialog><Toaster toastOptions={{ duration: Infinity }} /></>; }
  await act(() => root.render(<Example />));
  await act(() => { toast.error('Chưa lưu được', { description: 'Bạn hãy kiểm tra thư mục rồi thử lại.', action: { label: 'Thử lại', onClick: retry } }); }); await wait();
  const item = document.querySelector('[data-sonner-toast]')!;
  expect(item.querySelector('[data-description]')).toBeNull(); expect(item.querySelectorAll('[data-button]')).toHaveLength(1);
  await act(() => button('Chi tiết').click()); await wait();
  expect(item.getAttribute('data-type')).toBe('error');
  expect(document.querySelector('[role="region"]')?.textContent).toContain('kiểm tra thư mục');
  expect(document.querySelectorAll('[role="dialog"]')).toHaveLength(1);
  await act(() => { expect(dismissTopLayer()).toBe(true); }); await wait();
  expect(item.getAttribute('data-type')).toBe('error');
  expect(document.querySelector('[role="region"][data-state="open"]')).toBeNull();
  expect(document.querySelector('[role="dialog"][data-state="open"]')).not.toBeNull();
  await act(() => button('Chi tiết').click()); await wait();
  await act(() => button('Thử lại').click()); expect(retry).toHaveBeenCalledOnce();
  expect(toast.getToasts().every(item => !("title" in item) || item.delete || item.title !== 'Chưa lưu được')).toBe(true);
});

it("tiêu đề dài hiện đủ chữ (không cắt '…'); mô tả vào Chi tiết; hoàn tác vẫn bấm ngay", async () => {
  await act(() => root.render(<Toaster toastOptions={{ duration: Infinity }} />));
  const message = 'Đã thêm cuốn truyện có tên rất dài vào thư viện của bạn';
  await act(() => { toast.error(message, { description: 'Lý do đầy đủ nằm trong Chi tiết' }); }); await wait();
  const item = document.querySelector('[data-sonner-toast]')!;
  expect(item.querySelector('[data-title]')!.textContent).toBe(message);
  expect(item.querySelector('[data-description]')).toBeNull();
  await act(() => button('Chi tiết').click()); await wait();
  expect(document.querySelector('[role="region"]')?.textContent).toContain('Lý do đầy đủ nằm trong Chi tiết');
  const undo = vi.fn();
  await act(() => { toast.success(message, { id: 'undo', action: { label: 'Hoàn tác', onClick: undo } }); }); await wait();
  await act(() => button('Hoàn tác').click()); expect(undo).toHaveBeenCalledOnce();
});
