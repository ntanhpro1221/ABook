import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, MessageSquareQuote, SpellCheck, Users } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { Switch } from "@/desktop/PhoneSync";
import { PersonRow } from "@/listen/BookScreen";
import type { CastMember } from "@/listen/model";
import { useCast } from "@/listen/source";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { formatNumber } from "@/shared/format";
import { Button, EmptyState } from "@/shared/ui";
import { api, type BookSummary, type PrecastView } from "./api";
import { NameReadings } from "./NameReadings";
import {
  castItems,
  chapterRange,
  freeNote,
  lineCount,
  lineItems,
  nameItems,
  precastInvites,
  PRECAST_STEPS,
  TOP_PEOPLE,
  type PrecastStep,
} from "./precast";
import { nameKey, sameNames } from "./workText";
import { useWork, WorkCards } from "./WorkInbox";

// "Duyệt trước khi thu" (webui/precast.py, docs/STUDIO_REVIEW.md): ngay khi phân tích xong và trước khi thu tới những chương đầu,
// dẫn qua đúng thứ tự người duyệt cần - người nói nhiều nhất và giọng, cách đọc tên lạ, rồi "ai nói câu này" ở chương sắp thu.
// Mỗi bước là thẻ / dòng sẵn có của hộp việc và tab Nhân vật; bước nào cũng bỏ qua được. Không bước nào chặn dây chuyền: chỉ khi
// người dùng bật "Chờ tôi duyệt trước khi thu" thì sách đứng lại (tạm dừng) và chờ nút "Thu âm".

export function usePrecast(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["precast", bookId],
    enabled: Boolean(bookId) && enabled,
    queryFn: () => api<PrecastView>(`/api/books/${bookId}/precast`),
    refetchInterval: 15_000,
  });
}

/** Mã các thẻ việc đang nằm trong màn "Duyệt trước khi thu" (người và giọng, cách đọc tên, người nói ở chương sắp thu) - hộp "Việc
 *  cần duyệt" không hiện lại chúng (soát UX a8 05-10, mục 12: cùng một thẻ ở hai tab). Rỗng khi không có màn duyệt. */
export function usePrecastKeys(bookId: string, enabled: boolean): Set<string> | undefined {
  const { data: view } = usePrecast(bookId, enabled);
  const { data: work } = useWork(bookId);
  return useMemo(() => {
    if (!enabled || !view || !work) return undefined;
    const shown = [...castItems(work.items), ...nameItems(work.items), ...lineItems(work.items, view.upcoming.map((chapter) => chapter.id))];
    return new Set(shown.map((item) => item.key));
  }, [enabled, view, work]);
}

/** Công tắc "Chờ tôi duyệt trước khi thu" của một cuốn - ở trang dự án (trước mốc) và trên màn duyệt. */
export function PrecastWaitSwitch({ book, className }: { book: BookSummary; className?: string }) {
  const client = useQueryClient();
  const wait = Boolean(book.precast?.wait);
  const save = useMutation({
    mutationFn: (value: boolean) => api<PrecastView>(`/api/books/${book.id}/precast`, { method: "PUT", body: { wait: value } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["precast", book.id] });
      void client.invalidateQueries({ queryKey: ["book", book.id] });
      void client.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (error: Error) => toast.error("Chưa đổi được", { description: error.message }),
  });
  const passed = Boolean(book.precast?.announcedAt);
  const id = `precast-wait-${book.id}`;
  return (
    <label htmlFor={id} className={cn("flex items-start gap-3 rounded-xl border border-line bg-panel p-4", className)}>
      <Switch id={id} checked={wait} disabled={save.isPending} onCheckedChange={(value) => save.mutate(value)} />
      <span>
        <span className="block text-sm font-medium">Chờ tôi duyệt trước khi thu</span>
        <span className="mt-0.5 block text-[13px] leading-relaxed text-fg-2">
          {passed
            ? "Áp dụng cho lần phân tích xong của cuốn này - đã qua rồi. Muốn sách đứng lại lúc này thì bấm “Tạm dừng”."
            : wait
              ? "Phân tích xong, sách tạm dừng để bạn xem giọng, cách đọc tên và người nói - bấm “Thu âm” để thu tiếp."
              : "Phân tích xong thì thu luôn. Vẫn duyệt được bất cứ lúc nào; sửa ở chương chưa thu thì không phải thu lại."}
        </span>
      </span>
    </label>
  );
}

// Nút "Thu âm" (tạm dừng -> tiếp tục, không chạy lại gì) là nút chính ở đầu trang dự án (ProjectScreen Actions): màn này không
// thêm nút thứ hai cùng làm một việc (soát UX a8 05-10, mục 12).

function Intro({ book, view }: { book: BookSummary; view: PrecastView }) {
  return (
    <>
      <p className="mt-1 max-w-2xl text-pretty text-sm text-fg-2">
        Máy đã đọc hết truyện và phân vai. Xem nhanh những chỗ đáng sửa nhất trước khi thu - mỗi bước bỏ qua được, sửa xong máy áp từ
        chương sau. {freeNote(view)}
      </p>
      {/* Công tắc chỉ có nghĩa trước mốc (Studio mở màn này cả khi chưa kịp báo, vd app đóng lúc phân tích xong). */}
      {!book.precast?.announcedAt && !view.recordedChapters && <PrecastWaitSwitch book={book} className="mt-4 border-none bg-panel-2" />}
    </>
  );
}

const STEP_TITLE: Record<PrecastStep, string> = {
  cast: "Nhân vật và giọng",
  names: "Cách đọc tên",
  lines: "Ai nói câu này",
  done: "Xong",
};
const STEP_ICON = { cast: Users, names: SpellCheck, lines: MessageSquareQuote, done: ClipboardCheck } as const;

type Open = {
  onPickVoice: (person: CastMember) => void;
  onMerge: (person: CastMember) => void;
  onRename: (person: CastMember) => void;
  onGender: (person: CastMember) => void;
  onOpenReview: (card?: string) => void;
  onOpenScript: (chapterId: number, stableId: string, pick?: boolean, card?: string) => void;
  onOpenNames: (name: string, card?: string) => void;
  /** Rời màn duyệt (về tab Chương). */
  onClose: () => void;
  /** Bước đang mở nằm trong địa chỉ trang: nhảy sang Kịch bản rồi Back trở lại đúng bước. */
  step?: string | null;
  onStep: (step: PrecastStep) => void;
};

export function PrecastReview({ book, step: stepParam, onStep: setStep, ...open }: { book: BookSummary } & Open) {
  const { data: view } = usePrecast(book.id);
  const { data: work, isLoading } = useWork(book.id);
  const { data: cast } = useCast(book.id);
  const step: PrecastStep = PRECAST_STEPS.includes(stepParam as PrecastStep) ? (stepParam as PrecastStep) : "cast";
  // Điện thoại: bốn bước phải nằm ở màn đầu - lời giới thiệu và công tắc gập lại (soát UX a8 07-10).
  const narrow = useMediaQuery("(max-width: 639px)");
  if (!view || isLoading || !work) return <div className="mt-6 text-sm text-fg-2">Đang gom những gì cần duyệt…</div>;

  const people = (cast?.characters ?? []).slice(0, TOP_PEOPLE);
  // Nhiều dòng cùng tên ("Lính gác" ba lần) hầu như là một người máy tách ra theo từng chương - hỏi, và cho đường tắt tới chỗ gộp.
  const twins = sameNames(cast?.characters ?? []);
  const castCards = castItems(work.items);
  const nameCards = nameItems(work.items);
  const lineCards = lineItems(work.items, view.upcoming.map((chapter) => chapter.id));
  const range = chapterRange(view.upcoming);
  const counts: Record<PrecastStep, string> = {
    cast: castCards.length ? `${castCards.length} việc` : `${people.length} người`,
    names: nameCards.length ? `${nameCards.length} tên` : "ổn",
    lines: lineCards.length ? `${lineCount(lineCards)} câu` : "ổn",
    done: "",
  };
  const index = PRECAST_STEPS.indexOf(step);
  const next = () => setStep(PRECAST_STEPS[Math.min(index + 1, PRECAST_STEPS.length - 1)]);
  const cards = { book, onOpenReview: open.onOpenReview, onOpenScript: open.onOpenScript, onOpenNames: open.onOpenNames };

  return (
    <div className="mt-5">
      <div className="rounded-2xl border border-line bg-panel p-4 sm:p-5">
        <div className="min-w-0 max-w-2xl">
          <h2 className="text-base font-semibold">Duyệt trước khi thu</h2>
          {book.precast?.held && (
            <p className="mt-2 text-sm font-medium text-warning">Sách đang chờ bạn duyệt - duyệt xong bấm “Thu âm” ở đầu trang.</p>
          )}
        </div>
        {narrow ? (
          <details className="mt-2">
            <summary className="cursor-pointer text-sm text-fg-2">Giải thích và công tắc chờ duyệt</summary>
            <Intro book={book} view={view} />
          </details>
        ) : (
          <Intro book={book} view={view} />
        )}
      </div>

      <ol className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Các bước duyệt">
        {PRECAST_STEPS.map((value, position) => {
          const Icon = STEP_ICON[value];
          const active = value === step;
          return (
            <li key={value}>
              <button
                type="button"
                aria-current={active ? "step" : undefined}
                onClick={() => setStep(value)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-xl border p-3 text-left transition-colors",
                  active ? "border-accent/40 bg-accent-soft" : "border-line bg-panel hover:bg-hover",
                )}
              >
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold",
                    position < index ? "bg-success text-white" : active ? "bg-accent text-accent-ink" : "bg-hover text-fg-3",
                  )}
                >
                  {position < index ? <Check className="size-4" strokeWidth={3} /> : <Icon className="size-3.5" />}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold leading-tight">{STEP_TITLE[value]}</span>
                  {counts[value] && <span className="tabular block truncate text-xs text-fg-2">{counts[value]}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <section className="mt-5" aria-label={STEP_TITLE[step]}>
        {step === "cast" && (
          <>
            <p className="max-w-3xl text-sm text-fg-2">
              {people.length} người nói nhiều nhất - giọng của họ nghe suốt cuốn. Nghe thử câu mẫu; đổi giọng, đổi giới tính hay gộp
              hai tên của một người ngay trên dòng.
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {people.map((person) => (
                <div key={person.name} className="flex min-w-0 flex-col gap-1">
                  <PersonRow
                    bookId={book.id}
                    person={person}
                    onPickVoice={open.onPickVoice}
                    onMerge={open.onMerge}
                    onRename={open.onRename}
                    onGender={open.onGender}
                  />
                  {twins.has(nameKey(person.displayName)) && person.lines > 0 && (
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-1 text-xs text-fg-2">
                      <span>Cùng tên với người khác trong sách - một người?</span>
                      <Button size="sm" variant="ghost" onClick={() => open.onMerge(person)}>
                        Gộp vào…
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            {castCards.length > 0 && (
              <>
                <h3 className="mt-6 text-sm font-semibold">
                  Máy chưa chắc <span className="font-normal text-fg-2">· {castCards.length} việc về người và giọng</span>
                </h3>
                <WorkCards {...cards} items={castCards} />
              </>
            )}
          </>
        )}
        {step === "names" && (
          <>
            <p className="max-w-3xl text-sm text-fg-2">
              {nameCards.length
                ? `${nameCards.length} tên máy tự đoán cách đọc - tên máy kém chắc nhất ở trên. Nghe câu mẫu, sai thì sửa ngay trên thẻ.`
                : "Máy chắc cách đọc mọi tên đã gặp. Vẫn xem và sửa được từng tên ở danh sách dưới."}
            </p>
            {nameCards.length > 0 && <WorkCards {...cards} items={nameCards} />}
            <details className="mt-6 rounded-xl border border-line px-4 py-3">
              <summary className="cursor-pointer text-sm font-medium text-fg-2">Mọi cách đọc tên của cuốn</summary>
              <NameReadings bookId={book.id} />
            </details>
          </>
        )}
        {step === "lines" && (
          <>
            <p className="max-w-3xl text-sm text-fg-2">
              {lineCards.length
                ? `${formatNumber(lineCount(lineCards))} câu máy chưa chắc ai nói ở ${range || "những chương sắp thu"} - các chương thu đầu tiên.`
                : view.upcoming.length
                  ? `Máy không nghi ngờ câu nào ở ${range}.`
                  : "Mọi chương đã thu."}{" "}
              Thẻ ở các chương sau vẫn nằm trong “Việc cần duyệt”.
            </p>
            {lineCards.length > 0 && <WorkCards {...cards} items={lineCards} />}
          </>
        )}
        {step === "done" && (
          <EmptyState icon={ClipboardCheck} title="Xong lượt duyệt" className="py-10" action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button variant={book.precast?.held ? "ghost" : "secondary"} size="lg" onClick={open.onClose}>
                Về danh sách chương
              </Button>
            </div>
          }>
            {book.precast?.held
              ? "Sửa nào cũng đã ghi lại. Bấm “Thu âm” ở đầu trang để sách làm tiếp - máy áp các sửa ấy trước khi thu chương đầu tiên."
              : book.running
                ? "Sửa nào cũng đã ghi lại; máy áp ở chương kế tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."
                : "Sửa nào cũng đã ghi lại; máy áp khi sách chạy tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."}
          </EmptyState>
        )}
      </section>

      {step !== "done" && (
        <div className="mt-6 flex flex-wrap justify-end gap-2 border-t border-line pt-4">
          <Button variant="ghost" onClick={next}>
            Bỏ qua bước này
          </Button>
          <Button variant="primary" onClick={next}>
            Xong, sang {STEP_TITLE[PRECAST_STEPS[index + 1]].toLowerCase()}
          </Button>
        </div>
      )}
    </div>
  );
}

const INVITED_KEY = "abook-precast-invited-";

function invited(id: string): string | null {
  try {
    return localStorage.getItem(INVITED_KEY + id);
  } catch {
    return null;
  }
}

/** Lời mời "Phân tích xong - duyệt trước khi thu?" ở mọi trang của Studio, một lần mỗi mốc - cả Studio từ xa trên điện thoại
 *  (cùng giao diện này). Máy tính còn có thông báo Windows của Studio (webui/server.py `_precast_tick`). */
export function usePrecastInvites(books: BookSummary[] | undefined) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    for (const book of precastInvites(books ?? [], invited)) {
      try {
        localStorage.setItem(INVITED_KEY + book.id, String(book.precast?.announcedAt));
      } catch {
        /* không nhớ được thì lần sau mời lại - vô hại */
      }
      // Đang ở chính trang dự án ấy: dải mời trên trang đã nói, không cần thêm thông báo.
      if (pathname === `/studio/${book.id}`) continue;
      toast(book.precast?.held ? `“${book.title}” đang chờ bạn duyệt` : `“${book.title}” đã phân tích xong`, {
        id: `precast-${book.id}`,
        duration: 30_000,
        description: book.precast?.held
          ? "Sách tạm dừng trước khi thu. Xem giọng, cách đọc tên và người nói rồi bấm “Thu âm”."
          : "Duyệt giọng, cách đọc tên và người nói trước khi thu - sửa bây giờ thì không phải thu lại.",
        action: { label: "Duyệt", onClick: () => navigate(`/studio/${book.id}?tab=precast`) },
      });
    }
  }, [books, navigate, pathname]);
}

/** Dải mời trên trang dự án: phân tích xong, chưa thu bao nhiêu - mở màn duyệt (hay "Thu âm" khi sách đang chờ). */
export function PrecastBanner({ book, onOpen }: { book: BookSummary; onOpen: () => void }) {
  const held = Boolean(book.precast?.held);
  return (
    <div className={cn("mt-6 flex flex-wrap items-center gap-3 rounded-xl border p-4", held ? "border-warning/40 bg-warning-soft" : "border-accent/30 bg-accent-soft")}>
      <ClipboardCheck className={cn("size-5 shrink-0", held ? "text-warning" : "text-accent-text")} />
      <div className="min-w-0 flex-1 text-sm">
        <div className="font-semibold">{held ? "Phân tích xong - sách đang chờ bạn duyệt" : "Phân tích xong - duyệt trước khi thu?"}</div>
        <div className="text-fg-2">Giọng nhân vật, cách đọc tên, người nói ở các chương đầu: sửa bây giờ thì không phải thu lại.</div>
      </div>
      {/* Chờ duyệt: nút "Thu âm" đã là nút chính ở đầu trang (ProjectScreen Actions) - dải này chỉ mời duyệt, không thêm nút thứ hai. */}
      <div className="flex gap-2">
        <Button variant={held ? "secondary" : "primary"} onClick={onOpen}>
          Duyệt ngay
        </Button>
      </div>
    </div>
  );
}
