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

/** Sách chỉ-có-chữ (chưa chương nào có audio): không có độ dài audio để chia, nên tiến độ tính theo chương - chương nghe xong là 1, chương đang
 *  đọc dở là phần đã đọc trên độ dài ước của nó (`ChapterState.duration`, nếu đã ghi). Trước đây thanh tiến độ của sách chữ luôn 0. */
export function textBookProgress(state: ListeningState, chapters: ListenChapter[]): BookProgress {
  let sum = 0;
  let done = 0;
  let heard = 0;
  for (const chapter of chapters) {
    const record = state.chapters[String(chapter.id)];
    if (!record) continue;
    heard += record.heard || 0;
    if (record.done) {
      sum += 1;
      done += 1;
    } else if (record.duration && record.duration > 0) {
      sum += Math.min(1, Math.max(0, (record.heard || 0) / record.duration));
    }
  }
  const marked = Boolean(state.finished);
  const all = chapters.length > 0 && done === chapters.length;
  const fraction = chapters.length ? Math.min(1, sum / chapters.length) : 0;
  return { heardSeconds: heard, totalSeconds: 0, fraction: marked ? 1 : fraction, chaptersDone: done, finished: marked || all, caughtUp: false, rewound: false };
}
