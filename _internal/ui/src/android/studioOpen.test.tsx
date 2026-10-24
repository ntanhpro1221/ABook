import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ListenBook } from "@/listen/model";

// "Mở Studio" trên điện thoại (android/StudioOpen.tsx): plugin native và thông báo là bản giả - phần Kotlin có test JVM riêng (StudioLinkTest).
const library = vi.hoisted(() => ({
  studioComputers: vi.fn(async () => ({ computers: [] as { key: string; name: string; listenOnly?: boolean }[] })),
  openStudio: vi.fn(async (_options?: { computer?: string; book?: string }) => undefined),
}));
const toasts = vi.hoisted(() => Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }));
vi.mock("./plugins", () => ({ EbookLibrary: library, EbookPlayer: {}, ReadAloud: {} }));
vi.mock("sonner", () => ({ toast: toasts }));

import { ComputerList, OpenStudioButton, StudioChip, startStudio, studioChoice } from "./StudioOpen";

const home = { key: "", name: "NGDtuanh-Lecoo" };
const office = { key: "b2c3d4e5", name: "Máy văn phòng" };
const book = (over: Partial<ListenBook>) => ({ id: "b1", title: "Sách", ...over }) as ListenBook;

beforeEach(() => {
  library.studioComputers.mockReset();
  library.openStudio.mockClear();
  toasts.error.mockClear();
});

describe("Mở Studio của máy tính trên điện thoại", () => {
  it("một máy thì mở luôn, nhiều máy thì hỏi chọn, không máy nào thì nói rõ", () => {
    expect(studioChoice([home])).toEqual({ open: home });
    expect(studioChoice([home, office])).toEqual({ choose: [home, office] });
    expect(studioChoice([])).toEqual({ none: "Chưa ghép với máy tính nào" });
  });

  it("bấm nút: một máy tính mở thẳng máy ấy", async () => {
    library.studioComputers.mockResolvedValue({ computers: [office] });
    const choose = vi.fn();
    await startStudio(choose);
    expect(library.openStudio).toHaveBeenCalledWith({ computer: "b2c3d4e5" });
    expect(choose).not.toHaveBeenCalled();
  });

  it("bấm nút: hai máy tính thì hộp chọn hiện tên từng máy, chưa mở gì", async () => {
    library.studioComputers.mockResolvedValue({ computers: [home, office] });
    const choose = vi.fn();
    await startStudio(choose);
    expect(choose).toHaveBeenCalledWith([home, office]);
    expect(library.openStudio).not.toHaveBeenCalled();
    const html = renderToString(<ComputerList computers={[home, office]} onPick={() => undefined} />);
    expect(html).toContain("NGDtuanh-Lecoo");
    expect(html).toContain("Máy văn phòng");
  });

  it("bấm nút khi chưa ghép máy tính nào: báo, không mở", async () => {
    library.studioComputers.mockResolvedValue({ computers: [] });
    await startStudio(vi.fn());
    expect(toasts.error).toHaveBeenCalledWith("Chưa ghép với máy tính nào");
    expect(library.openStudio).not.toHaveBeenCalled();
  });

  it("nút ở tab Studio chỉ hiện khi có ít nhất một máy tính mở được Studio, kể cả chỉ ghép máy tính phụ", () => {
    expect(renderToString(<OpenStudioButton computers={[]} />)).toBe("");
    expect(renderToString(<OpenStudioButton computers={[office]} />)).toContain("Mở Studio");
    expect(renderToString(<OpenStudioButton computers={[home, office]} />)).toContain("Mở Studio");
  });

  it("chip ở trang sách chỉ có ở cuốn là dự án Studio của máy tính", () => {
    expect(renderToString(<StudioChip book={book({ studio: true })} />)).toContain("Mở Studio");
    expect(renderToString(<StudioChip book={book({ studio: false })} />)).toBe("");
    expect(renderToString(<StudioChip book={book({})} />)).toBe("");
  });
});

describe("máy tính chỉ cho điện thoại nghe", () => {
  const listenOnlyHome = { ...home, listenOnly: true };

  it("máy chỉ cho nghe không nằm trong lựa chọn; còn mỗi máy ấy thì nói vì sao", () => {
    expect(studioChoice([listenOnlyHome, office])).toEqual({ open: office });
    expect(studioChoice([listenOnlyHome])).toEqual({
      none: "Máy tính NGDtuanh-Lecoo chỉ cho nghe - trên máy tính ấy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”",
    });
  });

  it("nút mờ kèm lý do khi mọi máy tính chỉ cho nghe, không mở trang Studio đóng", async () => {
    const html = renderToString(<OpenStudioButton computers={[listenOnlyHome]} />);
    expect(html).toContain("disabled");
    expect(html).toContain("chỉ cho nghe - trên máy tính ấy, bật Cài đặt › Thiết bị");
    library.studioComputers.mockResolvedValue({ computers: [listenOnlyHome] });
    await startStudio(vi.fn());
    expect(library.openStudio).not.toHaveBeenCalled();
    expect(toasts.error).toHaveBeenCalledWith(expect.stringContaining("chỉ cho nghe"));
  });

  it("chip ở trang sách cũng mờ kèm lý do khi mọi máy tính chỉ cho nghe, và vẫn bấm được khi còn một máy mở được", () => {
    const html = renderToString(<StudioChip book={book({ studio: true })} computers={[listenOnlyHome]} />);
    expect(html).toContain("disabled");
    expect(html).toContain("Máy tính NGDtuanh-Lecoo chỉ cho nghe");
    const open = renderToString(<StudioChip book={book({ studio: true })} computers={[listenOnlyHome, office]} />);
    expect(open).not.toContain("disabled");
    expect(open).not.toContain("chỉ cho nghe");
  });

  it("chip đi tới máy GIỮ cuốn: mờ khi chính máy ấy chỉ cho nghe dù còn máy khác mở được, và mở được khi máy giữ cuốn mở được", () => {
    const holder = { ...listenOnlyHome, holdsBook: true };
    const blocked = renderToString(<StudioChip book={book({ studio: true })} computers={[holder, office]} />);
    expect(blocked).toContain("disabled");
    expect(blocked).toContain("Máy tính NGDtuanh-Lecoo chỉ cho nghe");
    expect(blocked).not.toContain("Máy văn phòng");
    const open = renderToString(<StudioChip book={book({ studio: true })} computers={[listenOnlyHome, { ...office, holdsBook: true }]} />);
    expect(open).not.toContain("disabled");
    expect(open).not.toContain("chỉ cho nghe");
  });

  it("nhiều máy cùng chỉ cho nghe: lý do nêu tên cả hai, hơn hai máy thì nói chung", () => {
    const second = { ...office, listenOnly: true };
    expect(studioChoice([listenOnlyHome, second])).toEqual({
      none: "Máy tính NGDtuanh-Lecoo và Máy văn phòng đều chỉ cho nghe - trên từng máy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”",
    });
    const third = { key: "c3", name: "Máy ba", listenOnly: true };
    const html = renderToString(<OpenStudioButton computers={[listenOnlyHome, second, third]} />);
    expect(html).toContain("Các máy tính đã ghép đều chỉ cho nghe");
    expect(html).not.toContain("Máy ba");
  });
});
