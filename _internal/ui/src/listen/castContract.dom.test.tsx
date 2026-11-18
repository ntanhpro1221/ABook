// @vitest-environment happy-dom
// Một đầu ra thật của máy chủ (tests/fixtures/cast_contract/cast.json, sinh bởi tests/test_cast_contract_fixture.py từ avatars.cast) vào tab
// Nhân vật của web: đúng chữ expected.json ghi - Qt (tst_cast_contract.qml) và Android (CastContractTest.kt) đọc cùng hai file.
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/shared/ui";
import cast from "../../../tests/fixtures/cast_contract/cast.json";
import expected from "../../../tests/fixtures/cast_contract/expected.json";
import invalid from "../../../tests/fixtures/cast_contract/invalid.json";
import { CastList } from "./BookScreen";
import { genderText, narratorRowLine, narratorRows, validCast } from "./castNarrator";
import type { Cast } from "./model";

const state = vi.hoisted(() => ({ cast: undefined as unknown }));
vi.mock("./player", async original => ({ ...await original<typeof import("./player")>(), usePlayer: () => ({ track: null, playing: false, toggle: vi.fn(), play: vi.fn() }), useNowPlaying: () => ({ setExpanded: vi.fn() }) }));
vi.mock("./clip", async original => ({ ...await original<typeof import("./clip")>(), useClip: () => ({ current: "", loading: false, toggle: vi.fn() }) }));
vi.mock("./source", async original => ({ ...await original<typeof import("./source")>(), useSource: () => ({ kind: "desktop", voiceUrl: () => "/voice.wav" }), useReadAloudVoices: () => ({ data: [] }), useCast: () => ({ data: state.cast }) }));

const view = cast as unknown as Cast;
const plain = (text: string | null | undefined) => text ?? "";

let root: Root, host: HTMLDivElement, client: QueryClient;
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); localStorage.clear();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 100, bottom: 24, width: 100, height: 24, toJSON() {} });
  vi.spyOn(HTMLElement.prototype, "animate").mockImplementation(() => ({ cancel: vi.fn(), onfinish: null }) as unknown as Animation);
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(() => root.unmount()); client.clear(); document.body.replaceChildren(); vi.restoreAllMocks(); });

it("the server's cast.json gives the narrator rows and gender cells every client shows", () => {
  const rows = narratorRows(view.narrator);
  expect(rows.map(row => ({ voice: row.voice, preset: row.preset, scope: row.scope, line: plain(narratorRowLine(row)) }))).toEqual(expected.narratorRows);
  const people = [...view.characters, ...view.extras];
  expect(Object.fromEntries(people.map(person => [person.displayName, genderText(person)]))).toEqual(expected.genders);
});

it("the Characters tab renders that output as the fold, the narrator rows and the gender cells", async () => {
  state.cast = view;
  await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>
    <CastList bookId="contract" onPickVoice={() => {}} /></TooltipProvider></MemoryRouter></QueryClientProvider>));
  const fold = [...host.querySelectorAll<HTMLButtonElement>("button[aria-controls]")].find(button => button.textContent?.startsWith(expected.narratorHeading))!;
  expect(plain(fold.textContent)).toContain(expected.narratorSummary);
  const rows = [...host.querySelectorAll('[data-testid="cast-narrator-row"]')];
  expect(rows).toHaveLength(expected.narratorRows.length);
  rows.forEach((row, index) => {
    const want = expected.narratorRows[index];
    for (const text of [want.voice, want.scope, want.line]) expect(plain(row.textContent)).toContain(text);
    expect(row.querySelector(`button[aria-label*="${want.voice}"]`), "nút nghe thử giọng").not.toBeNull();
  });
  const text = plain(host.textContent);
  for (const [name, gender] of Object.entries(expected.genders)) expect(text).toContain(name + gender);
});

it.each(invalid)("rejects $name with the shared state and leaves the book visible", async ({ cast: malformed }) => {
  expect(validCast(malformed)).toBe(false);
  state.cast = malformed;
  await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>
    <div>Trang sách</div><CastList bookId="invalid" /></TooltipProvider></MemoryRouter></QueryClientProvider>));
  expect(host.textContent).toContain("Trang sách");
  expect(host.textContent).toContain(expected.error.title);
  expect(host.textContent).toContain(expected.error.description);
  expect(host.querySelector('[data-testid="cast-narrator-row"]')).toBeNull();
});

it("contains an unexpected cast render exception within the book page", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  state.cast = { ...view, get narrator() { throw new Error("render failure"); } };
  await act(() => root.render(<QueryClientProvider client={client}><MemoryRouter><TooltipProvider>
    <div>Trang sách</div><CastList bookId="render-error" /></TooltipProvider></MemoryRouter></QueryClientProvider>));
  expect(host.textContent).toContain("Trang sách");
  expect(host.textContent).toContain(expected.error.title);
  expect(host.textContent).toContain(expected.error.description);
});
