import { renderToString } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

// Soát trợ năng a67: nút đang chạy vẫn nhận tiêu điểm, tiêu điểm đi theo nút mới khi nút cũ biến mất, mũi tên trong bảng nổi, tên nút mang giá
// trị, thanh "đã nghe" là progressbar. Không có DOM trong vitest - hàm thuần + renderToString + phần tử giả.

beforeAll(() => {
  const globals = globalThis as unknown as Record<string, unknown>;
  globals.window ??= Object.assign(new EventTarget(), {
    location: { search: "", hash: "", pathname: "/", origin: "http://127.0.0.1" },
    matchMedia: () => ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined }),
  });
});

describe("arrowTarget (Tốc độ / Giọng đọc / Hẹn giờ)", () => {
  it("xuống / phải sang mục sau, lên / trái về mục trước, Home / End, không vòng", async () => {
    const { arrowTarget } = await import("./ui");
    const items = ["a", "b", "c"];
    expect(arrowTarget(items, "a", "ArrowDown")).toBe("b");
    expect(arrowTarget(items, "b", "ArrowRight")).toBe("c");
    expect(arrowTarget(items, "c", "ArrowDown")).toBe("c");
    expect(arrowTarget(items, "a", "ArrowUp")).toBe("a");
    expect(arrowTarget(items, "c", "ArrowLeft")).toBe("b");
    expect(arrowTarget(items, "b", "Home")).toBe("a");
    expect(arrowTarget(items, "a", "End")).toBe("c");
    expect(arrowTarget(items, "a", "Tab")).toBeNull();
    // Tiêu điểm chưa ở mục nào: xuống vào mục đầu, lên vào mục cuối.
    expect(arrowTarget(items, null, "ArrowDown")).toBe("a");
    expect(arrowTarget(items, null, "ArrowUp")).toBe("c");
  });

  it("lên / xuống bỏ qua nút phụ cạnh mục (\"Thử\"), trái / phải thì vào được", async () => {
    const { arrowTarget } = await import("./ui");
    const items = ["hoai-my", "thu-hoai-my", "nam-minh", "thu-nam-minh"];
    const side = (item: string) => item.startsWith("thu-");
    expect(arrowTarget(items, "hoai-my", "ArrowDown", side)).toBe("nam-minh");
    expect(arrowTarget(items, "hoai-my", "ArrowRight", side)).toBe("thu-hoai-my");
    expect(arrowTarget(items, "thu-hoai-my", "ArrowDown", side)).toBe("nam-minh");
  });
});

describe("focusFollowTarget (Tải <-> Huỷ)", () => {
  const box = (found: Record<string, unknown>) => ({ querySelector: (selector: string) => found[selector] ?? null }) as unknown as Element;
  const body = { isConnected: true } as unknown as Element;

  it("nút đang giữ tiêu điểm bị gỡ: sang nút mới (data-focus-next), không có thì chỗ dự phòng", async () => {
    const { focusFollowTarget } = await import("./ui");
    const next = { id: "huy" };
    const fallback = { id: "tieu-de" };
    expect(focusFollowTarget(box({ "[data-focus-next]": next, "[data-focus-fallback]": fallback }), body, body)).toBe(next);
    expect(focusFollowTarget(box({ "[data-focus-fallback]": fallback }), null, body)).toBe(fallback);
    expect(focusFollowTarget(box({ "[data-focus-next]": next }), { isConnected: false } as unknown as Element, body)).toBe(next);
  });

  it("tiêu điểm còn ở một phần tử thật thì để nguyên", async () => {
    const { focusFollowTarget } = await import("./ui");
    expect(focusFollowTarget(box({ "[data-focus-next]": {} }), { isConnected: true } as unknown as Element, body)).toBeNull();
    expect(focusFollowTarget(null, null, body)).toBeNull();
  });
});

describe("nút đang chạy", () => {
  it("không disabled (còn nhận Tab), mang aria-disabled + aria-busy, bấm không làm gì", async () => {
    const { Button, busyClick } = await import("./ui");
    const html = renderToString(<Button loading disabled>Lưu</Button>);
    expect(html).toContain('aria-disabled="true"');
    expect(html).toContain('aria-busy="true"');
    expect(html).not.toMatch(/\sdisabled=""/);
    expect(renderToString(<Button disabled>Lưu</Button>)).toMatch(/\sdisabled=""/);
    const click = vi.fn();
    const event = { preventDefault: vi.fn() };
    busyClick(true, click)?.(event);
    expect(click).not.toHaveBeenCalled();
    expect(event.preventDefault).toHaveBeenCalled();
    busyClick(false, click)?.(event);
    expect(click).toHaveBeenCalledTimes(1);
  });
});

describe("tên đọc được", () => {
  it("thanh đã nghe là progressbar có giá trị", async () => {
    const { heardBarProps } = await import("./ui");
    // Làm tròn xuống như chữ "Đã nghe 42%" cạnh thanh (formatPercent) - trình đọc màn hình và mắt nghe / thấy cùng một số.
    expect(heardBarProps(0.426)).toMatchObject({ role: "progressbar", "aria-valuenow": 42, "aria-valuetext": "đã nghe 42%" });
    expect(heardBarProps(1.4)["aria-valuenow"]).toBe(100);
  });

  it("số đếm của tab đọc thành \"Chương, 6 mục\", không dính chữ", async () => {
    const { Tabs, TabsList, TabsTrigger } = await import("./ui");
    const html = renderToString(
      <Tabs value="chuong">
        <TabsList label="Mục">
          <TabsTrigger value="chuong" count={6}>Chương</TabsTrigger>
        </TabsList>
      </Tabs>,
    );
    const text = html.replace(/<[^>]+>/g, "").replace(/&#x27;/g, "'");
    expect(text).toContain("Chương, 6 mục");
  });

  it("phím tắt chỉ nói khi máy có bàn phím (máy tính)", async () => {
    const { nextChapterLabel, withShortcut } = await import("@/listen/labels");
    expect(withShortcut("Tắt tiếng", "M", true)).toBe("Tắt tiếng (M)");
    expect(withShortcut("Tắt tiếng", "M", false)).toBe("Tắt tiếng");
    expect(nextChapterLabel(true, true, false)).toBe("Chương sau");
  });
});

describe("nút Tốc độ / Giọng đọc của trình phát", () => {
  it("tên nút mang giá trị đang chọn", async () => {
    const { speedButtonLabel, voiceButtonLabel } = await import("@/listen/PlayerViews");
    expect(speedButtonLabel(1.2)).toBe("Tốc độ đọc: 1,2×");
    expect(voiceButtonLabel("Hoài My (Edge)")).toMatch(/^Giọng đọc: Hoài My/);
    expect(voiceButtonLabel(undefined)).toBe("Giọng đọc");
  });
});

describe("toastClearance (thông báo không che chỗ đang chọn)", () => {
  const toast = { top: 16, bottom: 100, left: 268, right: 624 };
  it("phần tử dưới thông báo ở trên: cuộn lên cho nó xuống dưới thông báo; ở dưới: cuộn xuống", async () => {
    const { toastClearance } = await import("./ui");
    expect(toastClearance({ top: 40, bottom: 88, left: 300, right: 360 }, [toast], 400)).toBe(40 - 100 - 8);
    const bottom = { top: 300, bottom: 384, left: 268, right: 624 };
    expect(toastClearance({ top: 320, bottom: 360, left: 300, right: 360 }, [bottom], 400)).toBe(360 - 300 + 8);
  });
  it("không chạm thông báo nào thì không cuộn", async () => {
    const { toastClearance } = await import("./ui");
    expect(toastClearance({ top: 192, bottom: 240, left: 231, right: 300 }, [toast], 400)).toBe(0);
    expect(toastClearance({ top: 40, bottom: 88, left: 100, right: 200 }, [toast], 400)).toBe(0);
    expect(toastClearance({ top: 40, bottom: 88, left: 300, right: 360 }, [], 400)).toBe(0);
  });
});
