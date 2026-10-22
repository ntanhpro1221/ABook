import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, it, vi } from "vitest";

// Soát a92 V1: thêm file nguồn trong lúc lượt quét mới còn chạy - nút Tạo đợi và không gửi danh sách nguồn cũ.

const ev = vi.hoisted(() => {
  const file = (path: string) => ({ path, name: path, title: path, firstLine: "", words: 18, chars: 64, audioSeconds: 6, credits: [], tailCredits: [] });
  const scan = (paths: string[]) => ({ files: paths.map(file), totals: { words: 18 * paths.length, chapters: paths.length, audioSeconds: 6 * paths.length }, skipped: [], missing: [] });
  return {
    states: [] as unknown[],
    seen: 0,
    create: vi.fn(),
    submit: null as null | (() => void),
    labels: [] as { text: unknown; disabled: unknown }[],
    scan,
    draft: { paths: ["old/1.txt", "new/2.txt"], title: "Sách thử", titleEdited: true, narrator: "Giọng thử", firstPerson: "", profile: "high_quality", startNow: true, excluded: [] },
  };
});
vi.mock("react", async (original) => {
  const actual = await original<typeof import("react")>();
  return {
    ...actual,
    // Hai lần useState đầu của trình tạo: nháp, rồi kết quả quét đang giữ.
    useState: (initial: unknown) => {
      ev.seen++;
      return ev.seen <= ev.states.length ? [ev.states[ev.seen - 1], vi.fn()] : actual.useState(initial);
    },
  };
});
vi.mock("react-router", () => ({ Link: () => null, useNavigate: () => vi.fn(), useSearchParams: () => [new URLSearchParams("step=3"), vi.fn()] }));
vi.mock("@/desktop/PhoneSync", () => ({ Switch: () => null }));
vi.mock("@/listen/clip", () => ({ useClip: () => ({}) }));
vi.mock("@/listen/source", () => ({ useSource: () => ({}) }));
vi.mock("@/shared/BookCover", () => ({ BookCover: () => null }));
vi.mock("@/shared/ui", () => ({
  Button: (p: { children: unknown; disabled?: boolean; variant?: string; onClick?: () => void }) => {
    if (p.variant === "primary" && typeof p.children === "string" && /Tạo|đọc nguồn/.test(p.children)) {
      ev.submit = p.onClick ?? null;
      ev.labels.push({ text: p.children, disabled: p.disabled });
    }
    return <button disabled={p.disabled}>{p.children as React.ReactNode}</button>;
  },
  LiveText: () => null, Segmented: () => null, Vu: () => null, radioGroupKeys: () => null, radioTabIndex: () => 0,
}));
vi.mock("@/studio/data", () => ({
  pickFiles: vi.fn(), pickFolder: vi.fn(), usePreferences: () => ({ data: {} }), useAppInfo: () => ({ data: { dialogs: true } }),
  useContinuation: () => ({}), useRedo: () => ({}), useCreateBook: () => ({ mutate: ev.create, isPending: false }),
  useFirstPersonHint: () => ({}), useScan: () => ({ isPending: true, mutate: vi.fn() }), useStudioMissing: () => ({ missing: false }),
  useVoices: () => ({ data: [{ name: "Giọng thử" }] }),
}));
vi.mock("@/studio/AnalysisModelPicker", () => ({
  AnalysisModelPicker: () => null, analysisChoiceLabel: () => "Mặc định", modelLabel: (x: string) => x,
  useAnalysisModels: () => ({ data: { default: "v5" } }), useAvailableModelNames: () => ["v5"],
}));
vi.mock("@/studio/StudioSetup", () => ({ NoStudioHere: () => null, StudioInstallNotice: () => null, useStudioFit: () => null, useStudioGpu: () => null }));
vi.mock("@/studio/TemplateBar", () => ({ TemplateBar: () => null }));
vi.mock("@/studio/VolumeSplit", () => ({ VolumeSplit: () => null }));
import { NewProjectScreen } from "./NewProjectScreen";
import { sourcesKey } from "./scanState";

beforeEach(() => {
  ev.seen = 0;
  ev.create.mockReset();
  ev.submit = null;
  ev.labels.length = 0;
});

it("nguồn vừa đổi, kết quả quét còn của danh sách cũ: nút Tạo đợi và không gửi gì", () => {
  ev.states = [ev.draft, { key: sourcesKey(["old/1.txt"]), result: ev.scan(["old/1.txt"]) }];
  const html = renderToStaticMarkup(<NewProjectScreen />);
  expect(html).toContain("Đang đọc nguồn…");
  expect(ev.labels.at(-1)).toEqual({ text: "Đang đọc nguồn…", disabled: true });
  ev.submit?.();
  expect(ev.create).not.toHaveBeenCalled();
});

it("quét xong đúng danh sách hiện tại: Tạo gửi đủ cả hai nguồn", () => {
  ev.states = [ev.draft, { key: sourcesKey(ev.draft.paths), result: ev.scan(ev.draft.paths) }];
  renderToStaticMarkup(<NewProjectScreen />);
  expect(ev.labels.at(-1)).toEqual({ text: "Tạo và bắt đầu", disabled: false });
  ev.submit!();
  expect(ev.create.mock.calls[0][0].paths).toEqual(["old/1.txt", "new/2.txt"]);
});

// Soát a92 T2: thời gian hứa ghi rõ là số tham khảo từ máy đã đo, không nhận là "máy này".
it("bước xác nhận: thời gian là số tham khảo và nói đo ở đâu", () => {
  ev.states = [ev.draft, { key: sourcesKey(ev.draft.paths), result: ev.scan(ev.draft.paths) }];
  const html = renderToStaticMarkup(<NewProjectScreen />);
  expect(html).toContain("Thời gian làm (tham khảo)");
  expect(html).toContain("máy của bạn có thể nhanh hơn hay chậm hơn");
  expect(html).not.toContain("Trên máy này");
});
