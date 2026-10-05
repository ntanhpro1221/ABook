import type { BookProgress, ListenChapter, ListeningState } from "@/listen/model";

/** Đã nghe bao nhiêu phần của cuốn - cùng phép tính với máy tính (abook/webui/listening.py): sách chưa đủ
 *  chương mà nghe hết phần đã có thì "đã theo kịp", chưa phải "nghe xong". */
export function bookProgress(state: ListeningState, chapters: ListenChapter[], complete = true): BookProgress {
  const total = chapters.reduce((sum, chapter) => sum + chapter.duration, 0);
  let heard = 0;
  let done = 0;
  for (const chapter of chapters) {
    const record = state.chapters[String(chapter.id)];
    if (!record) continue;
    if (record.done) {
      heard += chapter.duration;
      done += 1;
    } else {
      heard += Math.min(chapter.duration, record.heard || 0);
    }
  }
  const allHeard = chapters.length > 0 && done === chapters.length;
  const marked = Boolean(state.finished);
  const rewound = (marked || allHeard) && isRewound(state, chapters);
  if (rewound && state.last) heard = positionSeconds(state.last, chapters);
  return {
    heardSeconds: heard,
    totalSeconds: total,
    fraction: total ? heard / total : 0,
    chaptersDone: done,
    finished: !rewound && (marked || (complete && allHeard)),
    caughtUp: !rewound && !complete && allHeard && !marked,
    rewound,
  };
}

/** Gần đuôi chương bao nhiêu giây thì tính là nghe hết chương (DONE_TAIL_SECONDS của máy tính). */
const DONE_TAIL_SECONDS = 20;

/** Nghe hết rồi quay lại nghe một đoạn: chỗ nghe sau cùng không ở đuôi chương cuối và mới hơn lần tự đánh dấu nghe xong. */
function isRewound(state: ListeningState, chapters: ListenChapter[]): boolean {
  const last = state.last;
  if (!last || !chapters.length) return false;
  if (state.finished && (state.finishedAt ?? 0) >= (last.at ?? 0)) return false;
  const final = chapters[chapters.length - 1];
  if (last.chapterId !== final.id) return chapters.some((chapter) => chapter.id === last.chapterId);
  return final.duration > 0 && final.duration - last.seconds > DONE_TAIL_SECONDS;
}

function positionSeconds(last: { chapterId: number; seconds: number }, chapters: ListenChapter[]): number {
  let before = 0;
  for (const chapter of chapters) {
    if (chapter.id === last.chapterId) return before + Math.min(chapter.duration, last.seconds);
    before += chapter.duration;
  }
  return before;
}
