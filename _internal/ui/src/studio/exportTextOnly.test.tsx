import { renderToStaticMarkup } from "react-dom/server";
import { expect, it, vi } from "vitest";

// Soát a99 V5: dự án chỉ có chữ (chưa chương nào xong audio) xuất được `.abook` như bộ đóng gói hỗ trợ - nút không khoá, hộp nói file mang gì.
const state = vi.hoisted(() => ({ kind: "abook" }));
vi.mock("react", async (original) => {
  const actual = await original<typeof import("react")>();
  return { ...actual, useState: (initial: unknown) => actual.useState(initial === "mp3" ? state.kind : initial) };
});
vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined }),
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));
vi.mock("@/studio/data", () => ({
  useAppInfo: () => ({ data: { dialogs: true, remote: false, libraryRoot: "D:/Library" } }),
  useParts: () => ({ data: { parts: [] } }),
  pickFolder: vi.fn(),
}));
vi.mock("@/shared/ui", () => ({
  Dialog: ({ children }: any) => <div>{children}</div>,
  Button: ({ children, disabled, icon, loading, variant, ...rest }: any) => (
    <button disabled={disabled} {...rest}>
      {children}
    </button>
  ),
  LiveText: ({ shown }: any) => <span>{shown}</span>,
  Progress: () => <div />,
  radioGroupKeys: () => undefined,
  radioTabIndex: () => 0,
}));
vi.mock("@/desktop/AudiobookDialog", () => ({ FfmpegNeeded: () => null }));
vi.mock("@/desktop/ExportBookFileJob", () => ({ startExport: vi.fn(), trackExport: vi.fn() }));
vi.mock("@/studio/WordTimings", () => ({ WordTimingsRow: () => null }));
vi.mock("@/desktop/musicMix", () => ({ MusicMixOption: () => null, useMusicChoice: () => [false, vi.fn()] }));
import { ExportDialog } from "@/studio/ExportBook";

const textOnly = (total: number) =>
  ({ id: "b", title: "Sách chỉ chữ", running: false, pendingChanges: 0, chapters: { total, completed: 0, missingAudio: 0 } }) as any;
const render = (book: unknown) => renderToStaticMarkup(<ExportDialog book={book as any} open onOpenChange={() => {}} onApplyFirst={() => {}} />);

it("a text-only project can be exported as .abook, and the dialog says it carries the text", () => {
  state.kind = "abook";
  const html = render(textOnly(2));
  expect(html).toMatch(/<button(?![^>]*disabled)[^>]*>Chọn nơi lưu và xuất<\/button>/);
  expect(html).toContain("chỉ mang chữ");
});

it("a project with no chapters at all still cannot be exported as .abook", () => {
  state.kind = "abook";
  expect(render(textOnly(0))).toMatch(/<button[^>]*disabled=""[^>]*>Chọn nơi lưu và xuất<\/button>/);
});

it("MP3 stays blocked while no chapter has audio", () => {
  state.kind = "mp3";
  expect(render(textOnly(2))).toMatch(/<button[^>]*disabled=""[^>]*>Chọn nơi lưu và xuất<\/button>/);
});
