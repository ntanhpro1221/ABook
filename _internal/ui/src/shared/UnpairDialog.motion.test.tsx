import { expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ReactNode } from "react";
import { UnpairDialog } from "./UnpairDialog";
import { MotionPresence } from "./MotionPresence";
import type { UnpairCopy } from "./unpair";
vi.mock("./ui", () => ({ Dialog: ({ children }: { children: ReactNode }) => <section>{children}</section>, Button: ({ children }: { children: ReactNode }) => <button>{children}</button> }));
it("M98 lỗi gỡ ghép giữ role alert trong presence; thử lại đóng lớp lỗi, các nút vẫn còn", () => {
  const copy: UnpairCopy = { title: "Gỡ máy?", lines: [], discard: "Vẫn gỡ", cancel: "Huỷ", send: null, sendPrimary: false };
  const props = { copy, busy: null, onChoose: vi.fn(), onCancel: vi.fn() };
  const before = UnpairDialog({ ...props, error: "Chưa gửi được" });
  expect(renderToStaticMarkup(before)).toMatch(/role="alert"[^>]*>Chưa gửi được/);
  const after = UnpairDialog({ ...props, error: null });
  const presence = after.props.children[0].props.children.find((child: { type?: unknown }) => child?.type === MotionPresence);
  expect(presence.props.open).toBe(false); // Wrapper vẫn dựng để chạy exit sau commit.
  expect(renderToStaticMarkup(after)).toContain("Vẫn gỡ");
});
