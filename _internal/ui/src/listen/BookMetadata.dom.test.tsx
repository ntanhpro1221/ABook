// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { BookMetadataDetails, metadataOf } from "./BookMetadata";
import { bookMatchesQuery, type ListenBook } from "./model";

let dispose: (() => void) | undefined;
afterEach(() => { dispose?.(); vi.restoreAllMocks(); document.body.replaceChildren(); });

it("shows optional metadata and animates the full unabridged summary", async () => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel() {}, onfinish: null }) as unknown as Animation);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ height: 400 } as DOMRect);
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host); dispose = () => { void act(() => root.unmount()); };
  const summary = "Một chiếc thuyền giấy trôi quanh hồ nhỏ. ".repeat(20) + "\n\nĐoạn cuối nguyên vẹn.";
  await act(() => root.render(<BookMetadataDetails book={{ author: "Người Viết", illustrator: "Người Vẽ", altTitles: ["Paper Lake"], genres: ["Fantasy"], summary }} />));
  expect(host.textContent).toContain("Tác giả Người Viết");
  expect(host.textContent).toContain("Hoạ sĩ Người Vẽ");
  expect(host.querySelector('[aria-label="Thể loại"]')?.textContent).toBe("Fantasy");
  const toggle = host.querySelector("button")!;
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  const region = host.querySelector("[data-summary-state]")!;
  expect(region.getAttribute("data-summary-state")).toBe("closed");
  await act(() => toggle.click());
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(region.getAttribute("data-summary-state")).toBe("open");
  expect(host.textContent).toContain("Đoạn cuối nguyên vẹn.");
  expect(HTMLElement.prototype.animate).toHaveBeenCalled();
  await act(() => toggle.click());
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
});

it("omits missing metadata and finds an audiobook by its author", async () => {
  const host = document.createElement("div"); const root = createRoot(host); dispose = () => { void act(() => root.unmount()); };
  await act(() => root.render(<BookMetadataDetails book={{}} />));
  expect(host.textContent).toBe("");
  expect(bookMatchesQuery({ title: "Hồ giấy", author: "Người Viết", narrator: "" } as ListenBook, "nguoi viet")).toBe(true);
  expect(metadataOf({}).summary).toBe("");
});
