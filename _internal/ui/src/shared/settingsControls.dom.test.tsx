// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Button, ChoiceRow } from "./ui";
import { DisclosureRow } from "./DisclosureRow";
import { Fold } from "./Collapse";
import { MoreInfo, SettingsBlock } from "./SettingsNav";

let root: Root;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  const host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  localStorage.clear();
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true,
    value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("lựa chọn chữ giữ click, mũi tên, Home/End và một điểm Tab; không có nền chọn", async () => {
  function Choices() {
    const [value, change] = useState("a");
    return <ChoiceRow value={value} onChange={change} label="Màu" options={[{ value: "a", label: "Tự động" }, { value: "b", label: "Sáng" }, { value: "c", label: "Tối" }]} />;
  }
  await act(() => root.render(<Choices />));
  const radios = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="radio"]'));
  await act(() => radios[1].click());
  expect(radios[1].getAttribute("aria-checked")).toBe("true");
  await act(() => radios[1].dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
  expect(radios[2].getAttribute("aria-checked")).toBe("true");
  expect(document.activeElement).toBe(radios[2]);
  await act(() => radios[2].dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true })));
  expect(radios[0].tabIndex).toBe(0);
  expect(radios.filter(radio => radio.tabIndex === 0)).toHaveLength(1);
  expect(document.querySelector('[data-sliding-indicator="line"]')).not.toBeNull();
  expect(document.querySelector('[data-sliding-indicator="pill"]')).toBeNull();
});

it("Fold và khối Settings dùng cùng hàng, gập mở qua Collapse và nhớ trạng thái", async () => {
  await act(() => root.render(<><Fold storageKey="test.unified" title="Nhạc của tôi" summary="0 bài">Nội dung</Fold><SettingsBlock title="Chẩn đoán" fold="test.diagnostics">Nhật ký</SettingsBlock><MoreInfo>Giải thích</MoreInfo></>));
  const rows = Array.from(document.querySelectorAll<HTMLButtonElement>(".disclosure-row"));
  expect(rows).toHaveLength(3);
  expect(rows[0].className).toBe(rows[1].className);
  expect(rows[0].className).toBe(rows[2].className);
  const body = document.getElementById(rows[0].getAttribute("aria-controls")!)!;
  expect(body.hasAttribute("inert")).toBe(true);
  await act(() => rows[0].click());
  expect(body.dataset.state).toBe("open");
  expect(body.hasAttribute("inert")).toBe(false);
  expect(localStorage.getItem("abook.fold.test.unified")).toBe("1");
  expect(HTMLElement.prototype.animate).toHaveBeenCalled();
  await act(() => rows[0].click());
  expect(body.dataset.state).toBe("closed");
  expect(body.hasAttribute("inert")).toBe(true);
  expect(body.textContent).toBe("Nội dung");
  await act(() => rows[2].click());
  expect(document.getElementById(rows[2].getAttribute("aria-controls")!)!.dataset.state).toBe("open");
});

it("khoảng chữ bù theo mép nét, kể cả dấu nhô ra ngoài độ rộng ký tự", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ measureText: () => ({ actualBoundingBoxLeft: -1, actualBoundingBoxRight: 22, width: 20 }) } as unknown as CanvasRenderingContext2D);
  await act(() => root.render(<ChoiceRow label="Giới tính" value="f" onChange={() => {}} options={[{ value: "f", label: "Nữ" }]} />));
  const label = document.querySelector<HTMLSpanElement>('[role="radio"] > span')!;
  expect(label.style.marginInlineStart).toBe("-1px");
  expect(label.style.marginInlineEnd).toBe("2px");
});

it("hàng đi tới giữ route và trạng thái lịch sử", async () => {
  function Location() { const location = useLocation(); return <output>{location.pathname}:{location.state?.settingsList ? "có" : "không"}</output>; }
  await act(() => root.render(<MemoryRouter><DisclosureRow to="/settings/look" title="Giao diện" state={{ settingsList: true }} /><Location /></MemoryRouter>));
  await act(() => document.querySelector<HTMLAnchorElement>("a")!.click());
  expect(document.querySelector("output")!.textContent).toBe("/settings/look:có");
});

it("hàng disclosure chuyển tiếp sự kiện của trigger; nút chữ vẫn báo bận và giữ focus", async () => {
  const click = vi.fn(), pointer = vi.fn();
  await act(() => root.render(<><DisclosureRow title="Thành phần sử dụng" onPointerDown={pointer} onClick={click} data-state="closed" /><Button loading onClick={click}>Chép địa chỉ</Button></>));
  const [row, button] = Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
  await act(() => { row.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })); row.click(); button.click(); });
  expect(pointer).toHaveBeenCalledOnce(); expect(click).toHaveBeenCalledOnce();
  expect(button.dataset.variant).toBe("ghost"); expect(button.disabled).toBe(false);
  expect(button.getAttribute("aria-busy")).toBe("true");
  expect(row.dataset.state).toBe("closed");
});
