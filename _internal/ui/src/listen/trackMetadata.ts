import { useEffect, useRef, type MutableRefObject } from "react";
import type { CoverImage } from "@/shared/cover";
import { coverArtwork } from "@/shared/cover";
import type { NativeEngine } from "./engine";
import type { ListenBook, ListenChapter } from "./model";
import type { Track } from "./player";
import { useListenBook } from "./source";
import { withFreshSkips } from "./textScript";

/** Chỉ đổi nhãn; giữ nguyên nguồn phát, vị trí và hồ sơ nghe. */
export function useTrackMetadata(
  track: Track | null,
  refs: MutableRefObject<{ track: Track | null; queue: ListenChapter[]; book: { title: string } | null }>,
  setTrack: (track: Track) => void,
  setQueue: (queue: ListenChapter[]) => void,
  native: NativeEngine | null,
) {
  const { data: book } = useListenBook(track?.bookId);
  const nativeStamp = useRef("");
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
    if (refs.current.book) refs.current.book.title = book.title;
    if (native) {
      const stamp = JSON.stringify([book.id, book.title, book.narrator, book.cover, book.chapters?.map((chapter) => [chapter.id, chapter.fullTitle])]);
      if (stamp !== nativeStamp.current) {
        nativeStamp.current = stamp;
        native.updateMetadata?.(book);
      }
    }
    const next = metadataTrack(current, book, chapters);
    if (next === current) return;
    refs.current.track = next;
    setTrack(next);
    if (!native && "mediaSession" in navigator) {
      const artwork = next.bookCover ? new URL(next.bookCover.url, window.location.href).href : coverArtwork(next.bookTitle);
      navigator.mediaSession.metadata = new MediaMetadata({
        title: next.chapterTitle, album: next.bookTitle, artist: next.narrator,
        artwork: artwork ? [{ src: artwork, sizes: "512x512", type: "image/png" }] : [],
      });
    }
  }, [book, track?.bookId, refs, setTrack, setQueue, native]);
}

function metadataTrack(current: Track, book: ListenBook, chapters: ListenChapter[]): Track {
  const cover: CoverImage | null = book.cover ?? null;
  const chapterTitle = chapters.find((chapter) => chapter.id === current.chapterId)?.fullTitle ?? current.chapterTitle;
  if (current.bookTitle === book.title && current.narrator === book.narrator && current.chapterTitle === chapterTitle &&
      JSON.stringify(current.bookCover ?? null) === JSON.stringify(cover)) return current;
  return { ...current, bookTitle: book.title, bookCover: cover, narrator: book.narrator, chapterTitle };
}
