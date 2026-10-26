import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence } from "@/shared/MotionPresence";
import { Button } from "@/shared/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Hand, Moon, Play, Smartphone, TimerReset, X } from "lucide-react";
import { useMemo, useState } from "react";
import { cn } from "@/shared/cn";
import { formatClock } from "@/shared/format";
import { usePlayListenBook } from "./LibraryScreen";
import type { NightEvent, NightSession, Script } from "./model";
import { heardSinceNight } from "./night";
import { unquoted } from "./labels";
import { SpeakerLabel } from "./SpeakerLabel";
import { sentenceAt } from "./PlayerViews";
import { chapterScriptQuery, isMissing, useLastNight, useListenBook, useSource } from "./source";
import { useFadeScroller } from "@/shared/scrollFade";

// "Tối qua bạn nghe tới đâu?" - thẻ buổi sáng, chung cho máy tính và điện thoại.
//
// Không ai biết chính xác lúc người nghe thiếp đi. Nhưng nhật ký đêm có những mốc chắc chắn: lúc hẹn giờ, lần cuối
// còn chạm vào máy (chắc chắn còn thức), lúc điện thoại bắt đầu nằm yên (rất có thể là lúc ngủ - chỉ điện thoại có
// cảm biến), lúc tự dừng. Thẻ đặt CÂU VĂN đang được đọc ở mỗi mốc cạnh nhau: người nghe nhận ra đoạn cuối mình còn
// nhớ nhanh hơn nhiều so với nhìn một con số giây. Muốn chính xác hơn nữa thì lướt từng câu.

const RECENT_HOURS = 18;
const BEFORE_SLEEP_SECONDS = 120;

interface Marker {
  key: string;
  icon: typeof Moon;
  label: string;
  hint: string;
  at: number;
  chapterId: number;
  chapterTitle: string;
  seconds: number;
  suggested?: boolean;
}

/** "Tối qua" chỉ đúng khi lần hẹn giờ kết thúc hôm trước hay lúc rạng sáng; hẹn giờ ban ngày (06:5x sáng nay) thì không. */
function sessionLabel(endedAt: number | null | undefined): string {
  if (!endedAt) return "Tối qua";
  const ended = new Date(endedAt * 1000);
  const now = new Date();
  const today = ended.toDateString() === now.toDateString();
  return today && ended.getHours() >= 5 ? "Vừa hẹn giờ" : "Tối qua";
}

function timeOf(at: number): string {
  return new Date(at * 1000).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

function markersOf(session: NightSession): Marker[] {
  const events = session.events.filter((event) => event.position?.chapterId != null);
  const make = (event: NightEvent | undefined, key: string, icon: typeof Moon, label: string, hint: string, shift = 0): Marker | null =>
    event
      ? {
          key, icon, label, hint, at: event.at,
          chapterId: event.position.chapterId!, chapterTitle: event.position.chapterTitle,
          seconds: Math.max(0, event.position.seconds - shift),
        }
      : null;
  const timer = events.find((event) => event.type === "timer");
  const touches = events.filter((event) => event.type === "touch" || event.type === "shake" || event.type === "extend");
  const lastTouch = touches[touches.length - 1];
  const still = [...events].reverse().find((event) => event.type === "still");
  const stopped = [...events].reverse().find((event) => event.type === "stopped");
  const phone = session.device !== "desktop";
  const safety = timer?.action === "safety";
  const list = [
    safety ? null : make(timer, "timer", TimerReset, "Hẹn giờ ngủ", "chắc chắn còn thức"),
    lastTouch && lastTouch !== timer
      ? make(lastTouch, "touch", Hand, phone ? "Lần cuối chạm máy" : "Lần cuối dùng máy", "chắc chắn còn thức")
      : null,
    make(still, "still", Smartphone, "Máy bắt đầu nằm yên", "có lẽ đã ngủ từ khoảng này", BEFORE_SLEEP_SECONDS),
    make(stopped, "stopped", Moon, "Tự dừng", safety ? "không ai chạm máy suốt một lúc lâu" : "lúc hết giờ hẹn"),
  ].filter(Boolean) as Marker[];
  const suggested = list.find((marker) => marker.key === "still") ?? list.find((marker) => marker.key === "touch") ?? list[0];
  if (suggested) suggested.suggested = true;
  return list;
}

export function MorningRecap({ className }: { className?: string }) {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const source = useSource();
  const client = useQueryClient();
  const playBook = usePlayListenBook();
  const [scrubbing, setScrubbing] = useState(false);
  const { data } = useLastNight();
  const session = data?.night ?? null;
  const bookId = data?.bookId ?? "";
  const fresh = Boolean(
    session &&
      !session.dismissed &&
      session.endedAt &&
      session.events.some((event) => event.type === "stopped") &&
      Date.now() / 1000 - session.endedAt < RECENT_HOURS * 3600,
  );
  const markers = useMemo(() => (session && fresh ? markersOf(session) : []), [session, fresh]);
  const { data: book, error: bookError } = useListenBook(fresh && markers.length > 0 ? bookId : undefined);
  const ordered = book?.chapters ?? [];
  const markedIndices = markers.map(marker => ordered.findIndex(chapter => chapter.id === marker.chapterId)).filter(index => index >= 0);
  const range = markedIndices.length ? ordered.slice(Math.min(...markedIndices), Math.max(...markedIndices) + 1) : [];
  const chapterIds = range.length ? range.map(chapter => chapter.id) : [...new Set(markers.map(marker => marker.chapterId))];
  const scripts = useQuery({
    queryKey: ["listen", "night-scripts", bookId, chapterIds.join(",")],
    enabled: fresh && chapterIds.length > 0 && Boolean(book),
    // Cùng truy vấn với màn đọc (chapterScriptQuery): chương chỉ có chữ lấy chữ + mốc giọng máy đã đọc, không hỏi kịch bản sách nói mà
    // chương ấy không có (404 đỏ trong console).
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          chapterIds.map(async (id) => {
            const chapter = book?.chapters?.find((item) => item.id === id);
            return [id, chapter ? await client.fetchQuery(chapterScriptQuery(source, bookId, chapter)) : await source.script(bookId, id)] as const;
          }),
        ),
      ) as Record<number, Script>,
    staleTime: Infinity,
  });
  // Sách của đêm ấy đã bị xoá khỏi thư viện: không còn chỗ để nghe tiếp, ẩn thẻ. Đã nghe tiếp sau lúc tự dừng: thẻ không còn đúng,
  // cũng ẩn - chờ biết chỗ nghe của cuốn rồi mới hiện, đừng hiện rồi biến mất.
  if (!fresh || !session || !markers.length || isMissing(bookError)) return <MotionRegion />;
  if (!book ? !bookError : heardSinceNight(session.endedAt ?? 0, book.state.last?.at)) return <MotionRegion />;

  const dismiss = async () => {
    await source.dismissNight(bookId, session.id);
    void client.invalidateQueries({ queryKey: ["listen", "night"] });
  };
  const resume = async (chapterId: number, seconds: number) => {
    const book = await source.book(bookId);
    await playBook(book, chapterId, seconds);
    await dismiss();
  };
  const suggested = markers.find((marker) => marker.suggested)!;
  const script = scripts.data?.[suggested.chapterId];
  const indexAt = (script: Script, seconds: number) => {
    let found = 0;
    script.segments.forEach((segment, index) => {
      if ((segment.start ?? 0) <= seconds) found = index;
    });
    return found;
  };
  const scrub = chapterIds.flatMap((chapterId, index) => {
    const chapterScript = scripts.data?.[chapterId];
    if (!chapterScript?.timed) return [];
    const points = markers.filter(marker => marker.chapterId === chapterId).map(marker => marker.seconds);
    const from = index === 0 && points.length ? Math.max(0, indexAt(chapterScript, Math.min(...points)) - 2) : 0;
    const to = index === chapterIds.length - 1 && points.length ? indexAt(chapterScript, Math.max(...points)) + 3 : chapterScript.segments.length;
    return [{ chapterId, title: ordered.find(chapter => chapter.id === chapterId)?.fullTitle ?? markers.find(marker => marker.chapterId === chapterId)?.chapterTitle,
      segments: chapterScript.segments.slice(from, to) }];
  });

  return (
    <MotionRegion as="section" className={cn("relative py-4 sm:py-5", className)} aria-label={sessionLabel(session.endedAt)}>
      <button type="button" aria-label="Ẩn thẻ này" onClick={() => void dismiss()} className="touch-hit absolute right-[2px] top-2 grid size-9 place-items-center rounded-full text-fg-2 hover:bg-hover">
        <X className="size-4" />
      </button>
      {/* Nhãn HOA chỉ ≤ 3 chữ (DESIGN 5.5): tên sách xuống chữ thường 12 px, cắt bằng dấu ba chấm - không thành một dòng HOA dài. */}
      <div className="flex items-center gap-2 pr-11 text-accent-text">
        <Moon className="size-3.5 shrink-0" />
        <span className="label-section shrink-0">{sessionLabel(session.endedAt)}</span>
        <span className="min-w-0 truncate text-xs font-medium text-fg-2">· {session.bookTitle}</span>
      </div>
      <h2 className="mt-1.5 pr-11 text-lg font-semibold leading-snug">Nghe tới đâu rồi thiếp đi?</h2>

      {/* Nét ✕ và chữ "Tìm đúng câu" bù đệm nút (right-[2px], -mr-4) để chạm đúng mép chữ như giờ của các mốc. */}
      {/* Các mốc là hàng phẳng trong thẻ (không thẻ lồng thẻ - soát 24-10 V04): mốc gợi ý nổi bằng biểu tượng + tên màu nhấn, không khung. */}
      <ol className="mt-3 grid min-w-0 grid-cols-1 gap-x-6 gap-y-1 lg:grid-cols-2">
        {markers.map((marker) => {
          const sentence = sentenceAt(scripts.data?.[marker.chapterId], marker.seconds);
          return (
            <li key={marker.key} className="min-w-0">
              {/* data-recap-marker: như dòng menu, khoảng mực biểu tượng -> chữ bằng nhau mọi mốc (trăng khuyết nét tràn phải hơn bàn tay,
                  điện thoại 1,6 px - soát 25-10), styles.css. */}
              <button
                type="button"
                data-recap-marker=""
                onClick={() => void resume(marker.chapterId, marker.seconds)}
                className={cn(
                  "-mx-2 flex h-full w-[calc(100%+14px)] gap-3 rounded-control px-2 py-2.5 text-left transition-colors hover:bg-hover",
                )}
              >
                <marker.icon className={cn("mt-line-icon size-4 shrink-0", marker.suggested ? "text-accent-text" : "text-fg-2")} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className={cn("text-sm font-semibold", marker.suggested && "text-accent-text")}>{marker.label}</span>
                    <span className="tabular shrink-0 text-xs text-fg-2">{timeOf(marker.at)}</span>
                  </span>
                  <span className="block truncate text-xs text-fg-2">{marker.hint}</span>
                  <span className="tabular flex min-w-0 text-xs text-fg-2">
                    <span className="min-w-0 truncate">{marker.chapterTitle}</span>
                    <span className="shrink-0 whitespace-pre">{` · ${formatClock(marker.seconds)}`}</span>
                  </span>
                  {sentence && <span className="mt-1.5 line-clamp-2 block text-sm italic leading-snug text-fg">“{unquoted(sentence)}”</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void resume(suggested.chapterId, suggested.seconds)}
          className="touch-box flex h-11 flex-1 items-center justify-center gap-2 rounded-control bg-accent px-4 font-semibold text-accent-ink sm:flex-none"
        >
          <Play className="size-4" fill="currentColor" strokeWidth={0} /> Nghe từ đây
        </button>
        {script?.timed && (
          <Button variant="ghost" size="lg" onClick={() => setScrubbing((value) => !value)} className="touch-box -mr-4 rounded-control px-4 text-sm" aria-expanded={scrubbing}>
            {scrubbing ? "Thu gọn" : "Tìm đúng câu"}
          </Button>
        )}
      </div>

      <MotionPresence open={scrubbing && Boolean(script?.timed)}>
        {/* Vạch trên đúng mép chữ; vùng cuộn nới 7 px mỗi bên để hàng không bị cắt hay sinh cuộn ngang. */}
        {/* Lời dẫn đứng yên trên khung cuộn (không dính trong khung): mép trên mờ dần ngay dưới nó, không làm mờ chính nó. */}
        <div className="mt-4 border-t border-line"><p className="py-2 text-xs text-fg-2">Chọn câu cuối cùng còn nhớ:</p><div ref={scrollFade.ref} style={scrollFade.style} className="-mx-2 max-h-80 overflow-y-auto px-2">
          {scrub.map(group => <section key={group.chapterId} aria-label={group.title}>
            <h3 className="pb-1 pt-3 text-xs font-semibold text-fg-2">{group.title}</h3>
            {group.segments.map((segment) => (
            <button
              key={segment.id}
              type="button"
              onClick={() => void resume(group.chapterId, segment.start ?? 0)}
              className="-mx-2 block w-[calc(100%+14px)] rounded-control px-2 py-2.5 text-left text-[0.9375rem] leading-snug hover:bg-hover active:bg-hover"
            >
              {segment.speaker && <SpeakerLabel speaker={segment.speaker} sentence={segment.text} />}
              {segment.text}
            </button>
            ))}
          </section>)}
        </div></div>
      </MotionPresence>
    </MotionRegion>
  );
}
