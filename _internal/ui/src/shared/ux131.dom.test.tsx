// @vitest-environment happy-dom
import { act, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { Play } from "lucide-react";
import { Button, StatusPill, Tabs, TabsList, TabsTrigger } from "./ui";
import { MOTION } from "./motion";
import { readFileSync } from "node:fs";
import { cwd } from "node:process";
import { Fold } from "./Collapse";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  Object.defineProperty(CSSStyleDeclaration.prototype, Symbol.iterator, { configurable: true, value: function* (this: CSSStyleDeclaration) { for (let i = 0; i < this.length; i++) yield this.item(i); } });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  localStorage.clear();
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); document.head.replaceChildren(); vi.restoreAllMocks(); vi.useRealTimers(); });
const render = async (node: ReactNode) => { await act(() => root.render(node)); };
const snapshots = () => [...document.querySelectorAll<HTMLElement>(".motion-snapshot")];
const checkOld = (text: string) => {
  const old = snapshots().find(node => node.textContent?.includes(text));
  expect(old).toBeDefined(); expect(old?.hasAttribute("inert")).toBe(true); expect(old?.getAttribute("aria-hidden")).toBe("true"); expect(old?.style.pointerEvents).toBe("none");
};

it("nút đổi nhãn, số và icon giữ nút đang focus; ảnh cũ inert rồi tự gỡ", async () => {
  const click = vi.fn();
  await render(<Button icon={Play} onClick={click}>Áp dụng 2 việc</Button>);
  const button = host.querySelector("button")!; button.focus();
  await render(<Button icon={Play} loading onClick={click}>Đang áp dụng</Button>);
  expect(host.querySelector("button")).toBe(button); expect(document.activeElement).toBe(button);
  checkOld("Áp dụng 2 việc"); expect(button.getAttribute("aria-busy")).toBe("true");
  await act(() => button.click()); expect(click).not.toHaveBeenCalled();
  await render(<Button icon={Play} onClick={click}>Áp dụng 3 việc</Button>);
  checkOld("Đang áp dụng");
  await act(() => vi.advanceTimersByTime(MOTION.medium + 100)); expect(snapshots()).toHaveLength(0);
});

it("nút chỉ đổi con số vẫn fade", async () => {
  await render(<Button>Thu lại 2 câu</Button>);
  await render(<Button>Thu lại 3 câu</Button>);
  checkOld("Thu lại 2 câu");
});

for (const reduced of [false, true]) it(`trạng thái đổi nhãn/tone/VU rồi số thứ tự có fade, reduced=${reduced}`, async () => {
  vi.spyOn(window, "matchMedia").mockReturnValue({ matches: reduced } as MediaQueryList);
  await render(<StatusPill tone="muted" label="Xếp hàng · thứ 2" />);
  await render(<StatusPill tone="muted" label="Xếp hàng · thứ 3" />); checkOld("thứ 2");
  await render(<StatusPill tone="accent" live label="Đang thu" />); checkOld("thứ 3");
  expect(host.querySelector(".vu")).not.toBeNull();
  expect(HTMLElement.prototype.animate).toHaveBeenLastCalledWith([{ opacity: 0.45 }, { opacity: 1 }], expect.objectContaining({ duration: reduced ? MOTION.fast : MOTION.medium }));
  await render(<StatusPill tone="success" label="Hoàn tất" />); checkOld("Đang thu");
});

it("đếm trên tab có vào/đổi/ra, không thay trigger hoặc mất focus", async () => {
  const tab = (count?: number) => <Tabs defaultValue="work"><TabsList label="Dự án"><TabsTrigger value="work" count={count}>Việc</TabsTrigger></TabsList></Tabs>;
  await render(tab()); const trigger = host.querySelector<HTMLElement>('[role="tab"]')!; trigger.focus();
  await render(tab(1)); expect(trigger.textContent).toContain("1");
  await render(tab(2)); checkOld("1");
  await render(tab()); checkOld("2");
  expect(host.querySelector('[role="tab"]')).toBe(trigger); expect(document.activeElement).toBe(trigger);
  expect(trigger.textContent).not.toContain("mục");
});

it("tóm tắt Fold đổi mỗi con số vẫn fade, không mở hay mất focus", async () => {
  await render(<Fold storageKey="count" title="Nhân vật" summary="2 người">Nội dung</Fold>);
  const button = host.querySelector("button")!; button.focus();
  await render(<Fold storageKey="count" title="Nhân vật" summary="3 người">Nội dung</Fold>);
  checkOld("2 người"); expect(button.getAttribute("aria-expanded")).toBe("false"); expect(document.activeElement).toBe(button);
});

it("mọi điều khiển dùng màu/hover/focus ngắn từ token chung; reduced không scale nút", () => {
  const css = readFileSync(`${cwd()}/src/styles.css`, "utf8");
  // happy-dom chưa đọc @layer: đưa đúng rule nguồn vào CSSOM riêng.
  const sheet = new CSSStyleSheet(); sheet.replaceSync(css.match(/:where\(button, a, input[^}]+}/)![0]);
  const controls = sheet.cssRules[0] as CSSStyleRule;
  expect(controls.style.transitionProperty).toContain("outline-color");
  expect(controls.style.transitionDuration).toBe("var(--motion-fast)");
  expect(controls.style.transitionTimingFunction).toBe("var(--ease-standard)");
  expect(css).toContain("button:active { scale: none !important; }");
});
