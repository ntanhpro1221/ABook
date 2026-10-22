import { useCallback, useEffect, useRef, type MutableRefObject } from "react";
import type { CoverImage } from "@/shared/cover";
import { coverArtwork } from "@/shared/cover";
import type { NativeEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import type { Track } from "./player";
import { useListenBook } from "./source";
import { withFreshSkips } from "./textScript";

type LabelledBook = Pick<ListenBook, "id" | "title" | "narrator" | "cover">;

/** Nhãn lõi điện thoại đang giữ cho thẻ media: tên sách, giọng kể, bìa, tên các chương. */
interface NativeLabels { id: string; title: string; narrator: string; cover: string; chapters: readonly ListenChapter[] }

const labelsOf = (book: LabelledBook, chapters: readonly ListenChapter[] = []): NativeLabels =>
  ({ id: book.id, title: book.title, narrator: book.narrator, cover: JSON.stringify(book.cover ?? null), chapters });

/** Mọi loại chương (kể cả đọc to) dùng nhãn ở cấp trình phát. Đóng cuốn gỡ nhãn hệ điều hành. */
export function publishTrackMetadata(track: Track | null): void {
  if (!("mediaSession" in navigator)) return;
  if (!track) { navigator.mediaSession.metadata = null; return; }
  if (typeof MediaMetadata === "undefined") return;
  const artwork = track.bookCover ? new URL(track.bookCover.url, window.location.href).href : coverArtwork(track.bookTitle);
  navigator.mediaSession.metadata = new MediaMetadata({ title: track.chapterTitle, album: track.bookTitle, artist: track.narrator,
    artwork: artwork ? [{ src: artwork, sizes: "512x512", type: "image/png" }] : [] });
}

/** So từng chương chỉ khi danh sách chương đổi tham chiếu (react-query giữ nguyên tham chiếu khi dữ liệu không đổi). */
function sameLabels(a: NativeLabels | null, b: NativeLabels): boolean {
  return !!a && a.id === b.id && a.title === b.title && a.narrator === b.narrator && a.cover === b.cover && (a.chapters === b.chapters ||
    (a.chapters.length === b.chapters.length && a.chapters.every((chapter, index) => chapter.id === b.chapters[index].id && chapter.fullTitle === b.chapters[index].fullTitle)));
}

/** Chỉ đổi nhãn; giữ nguyên nguồn phát, vị trí và hồ sơ nghe. Trả về hàm gọi ngay trước `loadQueue` của điện thoại: lõi vừa nhận
 *  đúng những nhãn ấy, nên lần mở sách không gửi lại cả cuốn xuống lõi. */
export function useTrackMetadata(
  track: Track | null,
  refs: MutableRefObject<{ track: Track | null; queue: ListenChapter[]; book: { id: string; title: string } | null }>,
  setTrack: (track: Track) => void,
  setQueue: (queue: ListenChapter[]) => void,
  native: NativeEngine | null,
): (book: LabelledBook, chapters: readonly ListenChapter[]) => void {
  const { data: book } = useListenBook(track?.bookId);
  const nativeLabels = useRef<NativeLabels | null>(null);
  useEffect(() => {
    const current = refs.current.track;
    if (!book || !current || book.id !== current.bookId) return;
    const fresh = new Map(book.chapters?.map((chapter) => [chapter.id, chapter]));
    const skipped = withFreshSkips(refs.current.queue, book.chapters);
    const labelled = skipped.map((chapter) => {
      const updated = fresh.get(chapter.id);
      return updated && (updated.title !== chapter.title || updated.subtitle !== chapter.subtitle || updated.fullTitle !== chapter.fullTitle)
        ? { ...chapter, title: updated.title, subtitle: updated.subtitle, fullTitle: updated.fullTitle } : chapter;
    });
    const chapters = labelled.every((chapter, index) => chapter === skipped[index]) ? skipped : labelled;
    if (chapters !== refs.current.queue) {
      refs.current.queue = chapters;
      setQueue(chapters);
    }
    if (refs.current.book?.id === book.id) refs.current.book.title = book.title;
    if (native) {
      const labels = labelsOf(book, book.chapters);
      const changed = !sameLabels(nativeLabels.current, labels);
      nativeLabels.current = labels;
      if (changed) native.updateMetadata?.(book);
    }
    const next = metadataTrack(current, book, chapters);
    if (next === current) return;
    refs.current.track = next;
    setTrack(next);
    if (!native) publishTrackMetadata(next);
  }, [book, track?.bookId, refs, setTrack, setQueue, native]);
  return useCallback((loaded, chapters) => {
    nativeLabels.current = labelsOf(loaded, chapters);
  }, []);
}

function metadataTrack(current: Track, book: ListenBook, chapters: ListenChapter[]): Track {
  const cover: CoverImage | null = book.cover ?? null;
  const chapterTitle = chapters.find((chapter) => chapter.id === current.chapterId)?.fullTitle ?? current.chapterTitle;
  if (current.bookTitle === book.title && current.narrator === book.narrator && current.chapterTitle === chapterTitle &&
      JSON.stringify(current.bookCover ?? null) === JSON.stringify(cover)) return current;
  return { ...current, bookTitle: book.title, bookCover: cover, narrator: book.narrator, chapterTitle };
}
