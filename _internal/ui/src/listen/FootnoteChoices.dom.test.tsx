// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FootnoteChoices } from "./FootnoteChoices";
import { NO_FOOTNOTES, type FootnoteChoice } from "./textImport";

// Chú thích ở bước xem trước: cùng chữ, cùng thứ tự với điện thoại (addbook/AddBookScreen.kt) - "Bỏ số gọi", rồi "Lời chú" chọn một.

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); });

const offer = { found: 12, marks: 12, examples: [{ mark: "…trees²", note: "Lời chú về cây." }] };
const draw = (value: FootnoteChoice, onChange: (next: FootnoteChoice) => void, marks = offer.marks) =>
  act(() => root.render(<FootnoteChoices offer={{ ...offer, marks }} value={value} disabled={false} onChange={onChange} />));

it("dùng chữ của điện thoại: số gọi, rồi lời chú chọn một trong ba", async () => {
  await draw(NO_FOOTNOTES, vi.fn());
  expect(host.textContent).toContain("12 chú thích trong file");
  expect(host.textContent).toContain("Bỏ số gọi");
  expect(host.textContent).toContain("12 số gọi trong chữ");
  const group = host.querySelector('[role="radiogroup"]')!;
  expect(group.getAttribute("aria-label")).toBe("Lời chú");
  expect([...group.querySelectorAll("button")].map((button) => button.textContent)).toEqual(["Giữ nguyên", "Cuối chương", "Bỏ lời chú"]);
});

it("chọn một lời chú thì thay cái trước (một giá trị trong lõi), số gọi giữ nguyên", async () => {
  const onChange = vi.fn();
  await draw({ hideMarks: true, notes: "end" }, onChange);
  const drop = [...host.querySelectorAll('[role="radiogroup"] button')].find((button) => button.textContent === "Bỏ lời chú") as HTMLButtonElement;
  await act(() => drop.click());
  expect(onChange).toHaveBeenLastCalledWith({ hideMarks: true, notes: "drop" });
});

it("không có số gọi trong chữ thì không có ô bỏ số gọi", async () => {
  await draw(NO_FOOTNOTES, vi.fn(), 0);
  expect(host.textContent).not.toContain("Bỏ số gọi");
});
