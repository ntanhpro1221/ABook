// @vitest-environment happy-dom
import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import fixture from "../../../tests/fixtures/script_scope.json";
import { ScriptScope } from "./ScriptScope";
import type { ChapterScript, Line, Person } from "./ScriptTab";
import { S } from "@/shared/strings.generated";

let root: Root;
let host: HTMLDivElement;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  window.matchMedia = vi.fn().mockImplementation(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), finished: Promise.resolve() }) as unknown as Animation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); document.body.replaceChildren(); vi.restoreAllMocks(); });
const buttons = () => [...document.querySelectorAll<HTMLButtonElement>("button")];
const click = async (label: string) => { await act(() => {
  const button = buttons().find((item) => item.textContent?.includes(label));
  if (!button) throw new Error(`Missing ${label}: ${JSON.stringify(buttons().map((item) => item.textContent))}`);
  button.click();
}); };
const data = () => ({ chapterId: 1, index: 1, previous: null, next: null, firstPerson: null, title: "Chương thử", castReady: true, cast: [{ value: "OTHER", label: "Khách", lines: 1 }], others: [],
  scopeRevision: "revision", lines: fixture.lines as unknown as Line[] }) as ChapterScript;

function Entry({ script, apply }: { script: ChapterScript; apply: (lines: Line[], person: Person, revision: string) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>{S.s_scope_title}</button>{open && <ScriptScope script={script} line={script.lines[0]} onClose={() => setOpen(false)} onApply={apply} />}</>;
}

it("ten scene lines need two clicks after opening; k exceptions add k clicks", async () => {
  const script = data();
  // Ten speech rows with no private decisions, plus narration between them.
  script.lines = script.lines.map((line) => ({ ...line, wish: null, lineWish: null }));
  const apply = vi.fn().mockResolvedValue(undefined);
  await act(() => root.render(<Entry script={script} apply={apply} />));
  await click(S.s_scope_title);
  expect(apply).not.toHaveBeenCalled();
  expect(document.body.textContent).toContain(S.s_scope_count(10, 0));
  await click("Khách");
  const checks = [...document.querySelectorAll<HTMLButtonElement>('[role="checkbox"]')];
  await act(() => checks[1].click());
  await click(S.s_scope_apply);
  expect(apply).toHaveBeenCalledTimes(1);
  expect(apply.mock.calls[0][0].map((line: Line) => line.stableId)).toEqual(fixture.cases[1].ids.filter((id) => id !== "s001"));
  // Entry click + target + save = 3; this scenario has k=1, total 4.
});

it("a new person takes four actions for ten lines, without a source-text request", async () => {
  const script = data(); script.lines = script.lines.map((line) => ({ ...line, wish: null, lineWish: null }));
  const apply = vi.fn().mockResolvedValue(undefined);
  await act(() => root.render(<Entry script={script} apply={apply} />));
  await click(S.s_scope_title);
  const input = document.querySelector<HTMLInputElement>(`input[aria-label="${S.s_tim_nguoi_noi_70e3871e}"]`)!;
  await act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "Khách mới");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await click(S.s_khong_ro_8af7da78);
  await click(S.s_scope_apply);
  expect(apply.mock.calls[0][0]).toHaveLength(10);
  expect(apply.mock.calls[0][1]).toMatchObject({ value: "Khách mới", newGender: "unknown" });
});

it("keeps private wishes by default, exposes conflicts and opts in per line", async () => {
  const script = data(); const apply = vi.fn().mockResolvedValue(undefined);
  await act(() => root.render(<ScriptScope script={script} line={script.lines[0]} onClose={vi.fn()} onApply={apply} />));
  expect(document.body.textContent).toContain(S.s_scope_count(8, 2));
  const checks = [...document.querySelectorAll<HTMLButtonElement>('[role="checkbox"]')];
  expect(checks[2].getAttribute("aria-checked")).toBe("false");
  await act(() => checks[2].click());
  await click("Khách"); await click(S.s_scope_apply);
  expect(apply.mock.calls[0][0].map((line: Line) => line.stableId)).toContain("s002");
  expect(apply.mock.calls[0][0].map((line: Line) => line.stableId)).not.toContain("s004");
});

it("a changed preview shows an error and keeps the sheet open", async () => {
  const script = data(); const close = vi.fn();
  await act(() => root.render(<ScriptScope script={script} line={script.lines[0]} onClose={close} onApply={vi.fn().mockRejectedValue(new Error(S.s_scope_changed))} />));
  await click("Khách"); await click(S.s_scope_apply);
  expect(document.body.textContent).toContain(S.s_scope_changed);
  expect(close).not.toHaveBeenCalled();
});
