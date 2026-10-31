// @vitest-environment happy-dom
// Bài đo (docs/PERF_WEB.md mục 3): "Đọc theo" một chương 40.000 chữ (~2700 câu, ~900 đoạn, có mốc từng chữ). Cùng cách ghép như tab Đọc theo
// của màn Đang nghe (PlayerViews ReadAlong): câu đang nghe theo đồng hồ, khung tự cuộn theo giọng, chọn câu. Đo dựng, nhịp đồng hồ trong một câu
// (chữ đang đọc đổi), sang câu kế, nhảy xa, chọn câu.
import "./renderCount";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useCallback, useRef, useState } from "react";
import { MemoryRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Bench, installFakes } from "./harness";
import { Clock, ClockContext } from "@/listen/clock";
import type { Script, ScriptSegment } from "@/listen/model";

vi.mock("@/listen/player", async (original) => ({
  ...(await original<typeof import("@/listen/player")>()),
  usePlayer: () => ({ track: { bookId: "b", chapterId: 1 }, playing: true, jumpTo() {} }),
}));
vi.mock("@/listen/source", async (original) => ({ ...(await original<typeof import("@/listen/source")>()), useSource: () => ({ kind: "desktop" }) }));

const WORDS = 40_000;
const WORDS_PER_SENTENCE = 15;
const SENTENCES_PER_PARAGRAPH = 3;
/** Mỗi chữ 300 ms. */
const WORD_MS = 300;

function script(): Script {
  const vocabulary = ["người", "đi", "trên", "con", "đường", "dài", "gió", "thổi", "qua", "rừng", "núi", "xa", "xăm", "lặng", "im"];
  const segments: ScriptSegment[] = [];
  let word = 0;
  for (let index = 0; word < WORDS; index++) {
    const count = Math.min(WORDS_PER_SENTENCE, WORDS - word);
    const text = Array.from({ length: count }, (_, at) => vocabulary[(word + at) % vocabulary.length]).join(" ") + ".";
    const start = word * WORD_MS;
    const words = Array.from({ length: count }, (_, at) => [start + at * WORD_MS, start + (at + 1) * WORD_MS - 20] as [number, number]);
    const dialogue = index % 5 === 3;
    segments.push({ id: index + 1, paragraph: Math.floor(index / SENTENCES_PER_PARAGRAPH), text, kind: dialogue ? "dialogue" : "narration", speaker: dialogue ? "LAN" : "NARRATOR",
      start: start / 1000, end: (start + count * WORD_MS) / 1000, status: "done", words });
    word += count;
  }
  return { chapterId: 1, title: "Chương dài", timed: true, duration: (WORDS * WORD_MS) / 1000, segments };
}

let bench: Bench;
beforeEach(() => {
  installFakes();
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 700, bottom: 30, width: 700, height: 30, toJSON() {} });
});
afterEach(async () => {
  await bench?.unmount();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

it("đọc theo chương 40.000 chữ: nhịp đồng hồ chỉ vẽ lại câu đang đọc", async () => {
  const { ReadAlongText, usePlayingSentence, useFollowVoice } = await import("@/listen/ReadAlongText");
  const chapter = script();
  const clock = new Clock();
  let select: (index: number | null) => void = () => {};

  function Reading() {
    const container = useRef<HTMLDivElement | null>(null);
    const active = usePlayingSentence(chapter, true);
    const follow = useFollowVoice(container, active, { resetKey: "b:1", smooth: true });
    const [selected, setSelected] = useState<number | null>(null);
    select = setSelected;
    const after = useCallback(() => null, []);
    return (
      <div ref={container} onScroll={follow.onScroll} {...follow.input} className="reading-surface h-full overflow-y-auto">
        <ReadAlongText script={chapter} playingIndex={active} onTap={(index) => setSelected(index)} onWordMenu={() => {}} focusIndex={Math.max(0, active)}
          selected={selected} after={after} speakers dimHeard headingClassName="pb-2" className="space-y-5" />
      </div>
    );
  }

  bench = new Bench(`Đọc theo ${chapter.segments.length} câu / ${WORDS} chữ`, "Paragraph");
  clock.set(0.01, chapter.duration);
  await bench.mount(
    <QueryClientProvider client={new QueryClient()}>
      <ClockContext.Provider value={clock}>
        <MemoryRouter><Reading /></MemoryRouter>
      </ClockContext.Provider>
    </QueryClientProvider>,
  );
  const nodes = bench.nodes();
  // Giữa câu 100: mỗi nhịp 250 ms (đồng hồ của engine ~4 lần/giây) sang chữ kế hay giữ chữ.
  const middle = (100 * WORDS_PER_SENTENCE * WORD_MS) / 1000;
  await bench.phase("tới câu 100", () => clock.set(middle, chapter.duration));
  let time = middle;
  const words = await bench.phase("nhịp đồng hồ trong câu (×12)", () => clock.set((time += 0.25), chapter.duration), 12);
  let sentence = 101;
  const next = await bench.phase("sang câu kế (×10)", () => clock.set((sentence++ * WORDS_PER_SENTENCE * WORD_MS) / 1000 + 0.01, chapter.duration), 10);
  const jump = await bench.phase("nhảy xa (câu 2000)", () => clock.set((2000 * WORDS_PER_SENTENCE * WORD_MS) / 1000 + 0.01, chapter.duration));
  const choose = await bench.phase("chọn một câu", () => select(1500));
  await bench.phase("bỏ chọn", () => select(null));
  bench.report({ "nút DOM sau khi dựng": nodes, "số câu": chapter.segments.length });

  expect(words.watched).toBe(0);
  expect(next.watched).toBeLessThanOrEqual(2);
  // Nhảy xa: mọi đoạn vừa thành "đã nghe" nhạt đi (dimHeard) - đúng số đoạn đi qua, không hơn.
  expect(jump.watched).toBeLessThanOrEqual(Math.ceil((2000 - 110) / SENTENCES_PER_PARAGRAPH) + 2);
  expect(choose.watched).toBeLessThanOrEqual(2);
}, 180_000);
