import { useId, useLayoutEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { EASE, MOTION } from "@/shared/motion";
import { Reveal } from "@/shared/MotionPresence";
import { Button } from "@/shared/ui";
import { S } from "@/shared/strings.generated";
import type { ListenBook } from "./model";

export type BookMetadata = Pick<ListenBook, "author" | "illustrator" | "altTitles" | "genres" | "summary" | "source">;

export function metadataOf(book: BookMetadata): BookMetadata {
  return { author: book.author ?? "", illustrator: book.illustrator ?? "", altTitles: book.altTitles ?? [], genres: book.genres ?? [], summary: book.summary ?? "", source: book.source ?? { url: "", site: "" } };
}

export function BookMetadataDetails({ book }: { book: BookMetadata }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const paragraph = useRef<HTMLParagraphElement>(null);
  const region = useRef<HTMLDivElement>(null);
  const previousHeight = useRef<number | null>(null);
  const [fullHeight, setFullHeight] = useState(0);
  const [lineHeight, setLineHeight] = useState(24);
  useLayoutEffect(() => {
    const text = paragraph.current;
    if (!text) return;
    const measure = () => { setFullHeight(text.scrollHeight || text.getBoundingClientRect().height); setLineHeight(parseFloat(getComputedStyle(text).lineHeight) || 24); };
    measure();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure);
    observer?.observe(text);
    return () => observer?.disconnect();
  }, [book.summary]);
  const height = open ? fullHeight : Math.min(fullHeight || lineHeight * 3, lineHeight * 3);
  useLayoutEffect(() => {
    const from = previousHeight.current;
    previousHeight.current = height;
    if (from == null || from === height) return;
    const animation = region.current?.animate?.([{ height: `${from}px` }, { height: `${height}px` }], { duration: open ? MOTION.medium : MOTION.mediumOut, easing: open ? EASE.standard : EASE.accelerate });
    return () => animation?.cancel();
  }, [height, open]);
  if (!book.author && !book.illustrator && !book.altTitles?.length && !book.genres?.length && !book.summary) return null;
  return <div className="mt-2 space-y-3 text-sm">
    <Reveal when={book.author}><p className="text-fg-2">{S.s_tac_gia_0ec4731b} <span className="text-fg">{book.author}</span></p></Reveal>
    <Reveal when={book.illustrator}><p className="text-fg-2">{S.s_bookmeta_illustrator} <span className="text-fg">{book.illustrator}</span></p></Reveal>
    <Reveal when={book.altTitles?.length}><p className="break-words text-fg-2">{S.s_bookmeta_alt_titles} <span className="text-fg">{book.altTitles?.join("; ")}</span></p></Reveal>
    <Reveal when={book.genres?.length}><div aria-label={S.s_bookmeta_genres} className="flex flex-wrap gap-2">{book.genres?.map((genre, index) => <span key={`${index}-${genre}`} className="rounded-control bg-sunken px-2 py-1 text-xs text-fg-2">{genre}</span>)}</div></Reveal>
    <Reveal when={book.summary}><section aria-label={S.s_tom_tat_b4bb3064}>
      <h2 className="mb-2 font-medium">{S.s_tom_tat_b4bb3064}</h2>
      <div ref={region} id={id} data-summary-state={open ? "open" : "closed"} className="overflow-hidden" style={{ height: fullHeight ? height : open ? "auto" : "4.5em" }}>
        <p ref={paragraph} className="whitespace-pre-wrap break-words leading-relaxed text-fg-2">{book.summary}</p>
      </div>
      <Reveal when={fullHeight > lineHeight * 3 || !fullHeight && (book.summary?.length ?? 0) > 240}><Button variant="ghost" icon={open ? ChevronUp : ChevronDown} aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>{open ? S.s_thu_gon_1f6bf2c3 : S.s_xem_them_e0ac1b1e}</Button></Reveal>
    </section></Reveal>
  </div>;
}

export { BookMetadataFields } from "./BookMetadataFields";
