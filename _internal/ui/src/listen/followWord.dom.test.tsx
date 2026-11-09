// @vitest-environment happy-dom
import { act, useRef } from "react";
import { createRoot } from "react-dom/client";
import { beforeEach, expect, it, vi } from "vitest";

vi.mock("@/listen/LibraryScreen", () => ({ usePlayListenBook: () => vi.fn() }));
vi.mock("@/listen/player", () => ({ usePlayer: () => ({ track: null, jumpTo: vi.fn() }) }));
vi.mock("@/shared/motion", async (original) => ({ ...(await original<object>()), scrollMotion: (animate = true) => (animate ? "smooth" : "auto") }));
import { LIT_WORD_EVENT, useFollowVoice } from "./ReadAlongText";

// Chủ sách 09-11: "scroll chỉ thay đổi mỗi khi chuyển highlight đoạn chứ không đi theo highlight word" và "bấm vào tab đọc theo là nó bắt đầu scroll vội từ trên xuống".
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const VIEW = { top: 0, bottom: 600 };
function rect(top: number, height = 30) {
  return { top, bottom: top + height, left: 0, right: 100, width: 100, height, x: 0, y: top, toJSON: () => ({}) } as DOMRect;
}

function Reader({ index, onReady }: { index: number; onReady: (input: ReturnType<typeof useFollowVoice>) => void }) {
  const box = useRef<HTMLDivElement | null>(null);
  const follow = useFollowVoice(box, index, { smooth: true });
  onReady(follow);
  return (
    <div ref={box} data-testid="box">
      <span data-index="0"><span className="read-along-word is-lit">chữ</span></span>
    </div>
  );
}

let follow: ReturnType<typeof useFollowVoice>;
let box: HTMLElement;
let word: HTMLElement;
let scrollTo: ReturnType<typeof vi.fn>;

async function mount(sentenceTop: number, wordTop: number) {
  const host = document.createElement("div");
  document.body.append(host);
  scrollTo = vi.fn();
  const proto = HTMLElement.prototype as unknown as { scrollTo: unknown; getBoundingClientRect: unknown };
  proto.scrollTo = scrollTo;
  proto.getBoundingClientRect = function (this: HTMLElement) {
    if (this.dataset.testid === "box") return rect(VIEW.top, VIEW.bottom - VIEW.top);
    if (this.classList.contains("read-along-word")) return rect(wordTopNow);
    return rect(sentenceTop, 120);
  };
  wordTopNow = wordTop;
  const root = createRoot(host);
  await act(async () => root.render(<Reader index={0} onReady={(value) => { follow = value; }} />));
  box = host.querySelector<HTMLElement>("[data-testid=box]")!;
  word = host.querySelector<HTMLElement>(".read-along-word")!;
}

let wordTopNow = 0;
const nextWord = async (top: number) => {
  wordTopNow = top;
  await act(async () => { word.dispatchEvent(new Event(LIT_WORD_EVENT, { bubbles: true })); });
};

beforeEach(() => { document.body.innerHTML = ""; });

it("vào tab giữa chương: đứng ngay ở dòng đang đọc, không cuộn hoạt hoạ từ trên xuống", async () => {
  await mount(5000, 5060);
  expect(scrollTo).toHaveBeenCalledTimes(1);
  expect(scrollTo).toHaveBeenCalledWith({ top: 5060 - 180, behavior: "auto" });
});

it("chữ xuống dòng mới thì cuộn mượt đưa dòng ấy về một phần ba khung; cùng dòng thì đứng yên", async () => {
  await mount(5000, 5060);
  scrollTo.mockClear();
  await nextWord(5060);
  await nextWord(5062);
  expect(scrollTo).not.toHaveBeenCalled();
  await nextWord(5090);
  expect(scrollTo).toHaveBeenCalledTimes(1);
  expect(scrollTo).toHaveBeenCalledWith({ top: 5090 - 180, behavior: "smooth" });
});

it("người tự cuộn thì chữ đổi dòng không kéo khung đi nữa", async () => {
  await mount(5000, 5060);
  scrollTo.mockClear();
  await act(async () => { follow.input.onWheel(); });
  await nextWord(5120);
  expect(scrollTo).not.toHaveBeenCalled();
  expect(box).toBeTruthy();
});
