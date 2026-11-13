// @vitest-environment happy-dom
import { act, type ComponentProps } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SourceStep } from "./NewProjectScreen";
import { KEEP_CREDITS } from "./credits";

const h = vi.hoisted(() => ({ dialogs: true, files: vi.fn(), folder: vi.fn() }));
vi.mock("./data", async original => ({
  ...await original<typeof import("./data")>(),
  useAppInfo: () => ({ data: { dialogs: h.dialogs } }),
  pickFiles: h.files, pickFolder: h.folder,
}));
let host: HTMLDivElement, root: Root;
const selected = vi.fn();
const props: ComponentProps<typeof SourceStep> = {
  scan: null, title: "Part 2", onTitle: vi.fn(), scanning: false,
  onPaths: selected, onAddFiles: vi.fn(), onRemove: vi.fn(), total: 0,
  limit: null, later: 0, onLimit: vi.fn(), problem: null,
  dropCredits: KEEP_CREDITS, onDropCredits: vi.fn(), onSplit: vi.fn(),
  matter: { files: [], keep: [] }, onKeepMatter: vi.fn(),
  continuationId: "previous", pickContinuation: true, sourceHint: "D:/Stories/Original",
};
const draw = (over: Partial<typeof props> = {}) => act(() => root.render(<MemoryRouter><SourceStep {...props} {...over} /></MemoryRouter>));
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  h.dialogs = true; h.files.mockReset().mockResolvedValue([]); h.folder.mockReset().mockResolvedValue(null); selected.mockReset();
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null, finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); vi.restoreAllMocks(); document.body.replaceChildren(); });

it("opens the native picker at the hint and cancellation selects nothing", async () => {
  await draw();
  expect(h.files).toHaveBeenCalledExactlyOnceWith("Chọn chương mới", props.sourceHint);
  expect(selected).not.toHaveBeenCalled();
  await draw();
  expect(h.files).toHaveBeenCalledTimes(1);
});

it("uses only the files returned by the user's picker", async () => {
  h.files.mockResolvedValue(["D:/Elsewhere/003.txt"]);
  await draw();
  expect(selected).toHaveBeenCalledExactlyOnceWith(["D:/Elsewhere/003.txt"]);
});

it("does not open or probe a hint from a restored draft without a new continuation action", async () => {
  await draw({ pickContinuation: false });
  expect(h.files).not.toHaveBeenCalled();
  expect(selected).not.toHaveBeenCalled();
});

it("opens the browser picker for web Studio and Android instead of reading a host hint", async () => {
  h.dialogs = false;
  const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => {});
  await draw({ sourceHint: undefined });
  expect(click).toHaveBeenCalledTimes(1);
  expect((click.mock.contexts[0] as HTMLInputElement).type).toBe("file");
  expect(h.files).not.toHaveBeenCalled();
  expect(selected).not.toHaveBeenCalled();
});
