import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ dialog: null as null | { open: boolean; onOpenChange: (open: boolean) => void; title: unknown; description: unknown } }));
vi.mock("@/shared/ui", () => ({
  DialogActions: ({ children }: { children: unknown }) => <div>{children as never}</div>,
  Button: ({ children, onClick, disabled }: { children: unknown; onClick?: () => void; disabled?: boolean }) => <button disabled={disabled} onClick={onClick}>{children as never}</button>,
  Dialog: (props: NonNullable<typeof h.dialog> & { children?: unknown; footer?: unknown }) => {
    h.dialog = props;
    return <div data-dialog={String(props.open)}>{props.children as never}{props.footer as never}</div>;
  },
}));
import { ClearDialog } from "./ReadAloudStorage";
import { clearStorageQuestion, type ReadAloudCacheUsage } from "./prepareAhead";

// Xác nhận dọn bản đọc (soát a100 V4): hộp thoại dùng chung - Radix lo con trỏ vào hộp, Esc, trả con trỏ - chứ không phải khối nội tuyến.
const usage = { total: 3_000_000, books: [], bytes: 3_000_000 } as unknown as ReadAloudCacheUsage;
beforeEach(() => {
  h.dialog = null;
});

describe("ClearDialog", () => {
  it("là Dialog dùng chung, tên và lời hỏi đúng, mở theo `open`", () => {
    const html = renderToStaticMarkup(<ClearDialog open usage={usage} busy={false} onOpenChange={vi.fn()} onClear={vi.fn()} />);
    expect(h.dialog).toMatchObject({ open: true, title: "Dọn bản đọc đã làm", description: clearStorageQuestion(usage) });
    expect(html).toContain("Giữ lại");
    expect(html).toContain("Dọn");
    expect(html).not.toContain('role="alertdialog"');
  });

  it("Esc / bấm ra ngoài (onOpenChange(false)) đóng hộp khi chưa dọn", () => {
    const close = vi.fn();
    renderToStaticMarkup(<ClearDialog open usage={usage} busy={false} onOpenChange={close} onClear={vi.fn()} />);
    h.dialog!.onOpenChange(false);
    expect(close).toHaveBeenCalledWith(false);
  });

  it("đang dọn thì chưa đóng được, nút Giữ lại bị khoá", () => {
    const close = vi.fn();
    const html = renderToStaticMarkup(<ClearDialog open usage={usage} busy onOpenChange={close} onClear={vi.fn()} />);
    h.dialog!.onOpenChange(false);
    expect(close).not.toHaveBeenCalled();
    expect(html).toMatch(/<button disabled=""[^>]*>Giữ lại/);
  });
});
