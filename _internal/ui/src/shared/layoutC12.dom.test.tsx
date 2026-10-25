// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RemoteRow } from "@/android/DevicesScreen";
import { BookCover } from "./BookCover";
import { ScreenHeader } from "./ScreenHeader";
import { submenuOffsets } from "./menuPosition";
import { Select, TimeSelect } from "./ui";

let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("ô chọn trường chiếm cột; bộ giờ/phút dùng chiều rộng của một giá trị", async () => {
  await act(() => root.render(<><Select aria-label="Chuyển sang cuốn"><option>Sách A</option></Select><TimeSelect label="Từ" value="22:00" onChange={() => {}} /></>));
  const [field, time] = host.querySelectorAll("select");
  expect(field.dataset.selectLayout).toBe("column"); expect(field.classList.contains("w-full")).toBe(true);
  expect(time.dataset.selectLayout).toBe("inline"); expect(time.classList.contains("w-auto")).toBe(true);
});

// Soát ảnh 4x 26-10: thẻ đang tải hiện "Tải · 42%" trên bìa VÀ "42%" dưới tên - một thông tin hai chỗ. Dưới bìa chỉ còn nút Huỷ thẳng mép như nút Tải.
it("dưới bìa đang tải chỉ có nút Huỷ (tiến độ ở bìa), hàng thiết bị giữ ô số canh phải", async () => {
  const book = { id: "a", title: "Sách A", chaptersAvailable: 5, chaptersTotal: 5, duration: 300 };
  const progress = { bookId: "a", total: 100, done: 42 };
  await act(() => root.render(<><div data-case="compact"><RemoteRow compact book={book as never} progress={progress as never} onDownload={() => {}} /></div><div data-case="row"><RemoteRow book={book as never} progress={progress as never} onDownload={() => {}} /></div></>));
  const compact = host.querySelector('[data-case="compact"]')!, row = host.querySelector('[data-case="row"]')!;
  expect(compact.textContent).not.toContain("%");
  const cancel = compact.querySelector<HTMLButtonElement>('button[aria-label="Huỷ tải Sách A"]')!;
  expect(cancel.textContent?.trim()).toBe("Huỷ"); expect(cancel.classList.contains("edge-start-action")).toBe(true);
  expect(row.querySelector("[data-remote-progress]")?.textContent?.trim()).toBe("42%");
  expect(row.querySelector("[data-remote-progress]")?.classList.contains("text-right")).toBe(true);
});

it("ảnh chính và nền mờ đều giữ kích thước trước khi tải", async () => {
  await act(() => root.render(<BookCover title="Sách A" image={{ url: "/cover.jpg", width: 600, height: 900 }} />));
  expect(host.querySelectorAll("img")).toHaveLength(2);
  for (const image of host.querySelectorAll("img")) { expect(image.width).toBe(600); expect(image.height).toBe(900); }
});

it("tiêu đề màn con giữ đủ chữ và dùng cùng nút quay lại", async () => {
  const back = vi.fn(), title = "Tên chương rất dài của cuốn sách bạn đang nghe";
  await act(() => root.render(<ScreenHeader title={title} back={{ label: "Về Thư viện", onClick: back }} />));
  expect(host.querySelector("h1")?.textContent).toBe(title); expect(host.querySelector("h1")?.classList.contains("truncate")).toBe(false);
  expect(host.querySelector("button svg.lucide-arrow-left")).not.toBeNull();
  await act(() => host.querySelector("button")!.click()); expect(back).toHaveBeenCalledOnce();
});

it("menu con lấy khe 8 px từ bảng cha, cả đỉnh/đáy và hai phía; giữ số lẻ CSS", () => {
  const parent = document.createElement("div"), row = document.createElement("button");
  parent.setAttribute("role", "menu"); parent.dataset.side = "bottom"; parent.append(row); host.append(parent);
  const box = (left: number, top: number, width: number, height: number) => ({ x:left, y:top, left, top, right:left+width, bottom:top+height, width, height, toJSON() {} });
  parent.getBoundingClientRect = () => box(100.25, 120.5, 240, 300);
  row.getBoundingClientRect = () => box(112.25, 330.5, 216, 40);
  expect(submenuOffsets(row, "right", "start")).toEqual({ sideOffset:20, alignOffset:-210 });
  expect(submenuOffsets(row, "left", "end")).toEqual({ sideOffset:20, alignOffset:-50 });
  expect(submenuOffsets(null, "left", "end")).toBeNull();
  parent.style.transform = "matrix(0.5,0,0,0.5,0,0)";
  vi.stubGlobal("DOMMatrixReadOnly", class { a = .5; d = .5; });
  expect(submenuOffsets(row, "right", "start")).toEqual({ sideOffset:32, alignOffset:-420 });
});
