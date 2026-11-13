import { S } from "../shared/strings.generated";
import { MoreInfo, SettingsRow } from "@/shared/SettingsNav";
import { MotionRegion } from "@/shared/MotionRegion";
import { MotionPresence, Reveal } from "@/shared/MotionPresence";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCheck, MessageSquareQuote, SpellCheck, Users } from "lucide-react";
import { useMemo, useRef } from "react";
import { toast } from "@/shared/toast";
import { Switch } from "@/desktop/Switch";
import { PersonRow } from "@/listen/BookScreen";
import type { CastMember } from "@/listen/model";
import { useCast } from "@/listen/source";
import { cn } from "@/shared/cn";
import { useMediaQuery } from "@/shared/media";
import { formatNumber } from "@/shared/format";
import { Button, EmptyState, ContentSkeleton, InlineError } from "@/shared/ui";
import { api, type BookSummary, type PrecastView } from "./api";
import { NameReadings } from "./NameReadings";
import { pollDelay, retryUnlessGone } from "./polling";
import {
  castItems,
  chapterRange,
  freeNote,
  lineCount,
  lineItems,
  nameItems,
  precastKeys,
  PRECAST_STEPS,
  TOP_PEOPLE,
  type PrecastStep,
} from "./precast";
import { nameKey, sameNames } from "./workText";
import { useCardFocus, type CardFocusEnds } from "./useCardFocus";
import { useWork, WorkCards } from "./WorkInbox";
import type { WorkLists } from "./workFocus";

// "Duyệt trước khi thu" (webui/precast.py, docs/STUDIO_REVIEW.md): ngay khi phân tích xong và trước khi thu tới những chương đầu,
// dẫn qua đúng thứ tự người duyệt cần - người nói nhiều nhất và giọng, cách đọc tên lạ, rồi "ai nói câu này" ở chương sắp thu.
// Mỗi bước là thẻ / dòng sẵn có của hộp việc và tab Nhân vật; bước nào cũng bỏ qua được. Không bước nào chặn dây chuyền: chỉ khi
// người dùng bật "Duyệt trước khi thu" thì sách đứng lại (tạm dừng) và chờ nút "Thu âm".

export function usePrecast(bookId: string, enabled = true) {
  return useQuery({
    queryKey: ["precast", bookId],
    enabled: Boolean(bookId) && enabled,
    queryFn: () => api<PrecastView>(`/api/books/${bookId}/precast`),
    retry: retryUnlessGone,
    refetchInterval: (query) => pollDelay(15_000, query.state),
  });
}

/** Mã các thẻ việc đang nằm trong màn "Duyệt trước khi thu" (người và giọng, cách đọc tên, người nói ở chương sắp thu) - hộp "Việc
 *  cần duyệt" không hiện lại chúng (soát UX a8 05-10, mục 12: cùng một thẻ ở hai tab). Rỗng khi không có màn duyệt. */
export function usePrecastKeys(bookId: string, enabled: boolean): Set<string> | undefined {
  const { data: view } = usePrecast(bookId, enabled);
  const { data: work } = useWork(bookId, enabled);
  return useMemo(() => {
    if (!enabled || !view || !work) return undefined;
    return precastKeys(work.items, view.upcoming.map((chapter) => chapter.id));
  }, [enabled, view, work]);
}

/** Công tắc "Duyệt trước khi thu" của một cuốn - ở trang dự án (trước mốc) và trên màn duyệt. */
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
    onError: (error: Error) => toast.error(S.s_chua_doi_duoc_a6c67cde, { description: error.message }),
  });
  const passed = Boolean(book.precast?.announcedAt);
  const id = `precast-wait-${book.id}`;
  return (
    <div className={className}>
      <SettingsRow
        label={<span id={`${id}-name`}>{S.s_duyet_truoc_khi_thu_74c121d0}</span>}
        hint={
          <span id={`${id}-hint`}>
            {passed
              ? S.s_phan_tich_da_xong_muon_dung_thi_bam_tam_du_73416c6b
              : wait
                ? S.s_dung_sau_phan_tich_de_ban_duyet_roi_bam_th_0ca451d3
                : S.s_phan_tich_xong_thi_thu_luon_duyet_luc_nao_1f91e9f9}
          </span>
        }
      >
        <Switch id={id} labelledBy={`${id}-name`} describedBy={`${id}-hint`} checked={wait} disabled={save.isPending} onCheckedChange={(value) => save.mutate(value)} />
      </SettingsRow>
    </div>
  );
}

// Nút "Thu âm" (tạm dừng -> tiếp tục, không chạy lại gì) là nút chính ở đầu trang dự án (ProjectScreen Actions): màn này không
// thêm nút thứ hai cùng làm một việc (soát UX a8 05-10, mục 12).

function Intro({ book, view }: { book: BookSummary; view: PrecastView }) {
  return (
    <>
      <p className="mt-1 max-w-2xl text-pretty text-sm text-fg-2">{S.s_duyet_nhanh_truoc_khi_thu_co_the_bo_qua_tu_d3a2f0a0}</p>
      <MoreInfo label={S.s_khi_ap_dung_017de1f0}>{freeNote(view)}</MoreInfo>
      {/* Công tắc chỉ có nghĩa trước mốc (Studio mở màn này cả khi chưa kịp báo, vd app đóng lúc phân tích xong). */}
      <MotionPresence open={!book.precast?.announcedAt && !view.recordedChapters}><PrecastWaitSwitch book={book} className="mt-2" /></MotionPresence>
    </>
  );
}

/** Hết thẻ ở bước đang mở thì tiêu điểm về đầu vùng của bước (không có dòng báo cuối riêng). */
const PRECAST_ENDS: CardFocusEnds = { end: "precast-end", lead: "precast-step" };

const STEP_TITLE: Record<PrecastStep, string> = {
  cast: S.s_nhan_vat_va_giong_52dfc919,
  names: S.s_cach_doc_ten_1c46e75d,
  lines: S.s_ai_noi_cau_nay_0e00a5c7,
  done: S.s_xong_a6f4543a,
};
const STEP_ICON = { cast: Users, names: SpellCheck, lines: MessageSquareQuote, done: ClipboardCheck } as const;

type Open = {
  onPickVoice: (person: CastMember) => void;
  onMerge: (person: CastMember) => void;
  onUnmerge: (person: CastMember) => void;
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
  const precast = usePrecast(book.id);
  const { data: view } = precast;
  const workQuery = useWork(book.id);
  const { data: work, isLoading } = workQuery;
  const castQuery = useCast(book.id);
  const { data: cast } = castQuery;
  const step: PrecastStep = PRECAST_STEPS.includes(stepParam as PrecastStep) ? (stepParam as PrecastStep) : "cast";
  // Điện thoại: bốn bước phải nằm ở màn đầu - lời giới thiệu và công tắc gập lại (soát UX a8 07-10).
  const narrow = useMediaQuery("(max-width: 639px)");
  // Quyết xong một thẻ thì thẻ rời danh sách: tiêu điểm sang thẻ kế (hết thẻ thì về đầu vùng bước), không rơi về BODY (useCardFocus.ts).
  const lists = useRef<WorkLists | null>(null);
  useCardFocus(lists, PRECAST_ENDS);
  if ((precast.isError && !view) || (workQuery.isError && !work) || (castQuery.isError && !cast)) return <MotionRegion fadeThrough><InlineError className="mt-6" message={S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_luot_971eabb5} onRetry={() => { void precast.refetch(); void workQuery.refetch(); void castQuery.refetch(); }} /></MotionRegion>;
  if (!view || isLoading || !work || !cast) return <MotionRegion fadeThrough><ContentSkeleton shape="cards" className="mt-6" label={S.s_dang_tai_luot_duyet_c2e5bf3f} /></MotionRegion>;

  const people = (cast?.characters ?? []).slice(0, TOP_PEOPLE);
  // Nhiều dòng cùng tên ("Lính gác" ba lần) hầu như là một người máy tách ra theo từng chương - hỏi, và cho đường tắt tới chỗ gộp.
  const twins = sameNames(cast?.characters ?? []);
  const castCards = castItems(work.items);
  const nameCards = nameItems(work.items);
  const lineCards = lineItems(work.items, view.upcoming.map((chapter) => chapter.id));
  const range = chapterRange(view.upcoming);
  const counts: Record<PrecastStep, string> = {
    cast: castCards.length ? S.s_0_viec_d6b72911(castCards.length) : S.s_0_nguoi_272b4f6d(people.length),
    names: nameCards.length ? S.s_0_ten_f2f08473(nameCards.length) : S.s_ten_nao_cung_on_095d4866,
    lines: lineCards.length ? S.s_0_cau_2a1e6590(lineCount(lineCards)) : S.s_khong_cau_nao_nghi_25d773f7,
    done: "",
  };
  lists.current = { open: (step === "cast" ? castCards : step === "names" ? nameCards : step === "lines" ? lineCards : []).map((item) => item.key), decided: [] };
  const index = PRECAST_STEPS.indexOf(step);
  const next = () => setStep(PRECAST_STEPS[Math.min(index + 1, PRECAST_STEPS.length - 1)]);
  const cards = { book, onOpenReview: open.onOpenReview, onOpenScript: open.onOpenScript, onOpenNames: open.onOpenNames };

  return (
    <MotionRegion as="div" className="mt-5">
      {/* Phẳng, không khung, không lặp tên tab làm tiêu đề (DESIGN 6 "Tab trong trang"; soát 24-10): tiêu đề chỉ cho trình đọc màn hình. */}
      <div>
        <div className="min-w-0 max-w-2xl">
          <h2 className="sr-only">{S.s_duyet_truoc_khi_thu_74c121d0}</h2>
          {book.precast?.held && (
            <p className="text-sm font-medium text-warning">{S.s_sach_dang_cho_ban_duyet_duyet_xong_bam_thu_f9900395}</p>
          )}
        </div>
        {narrow ? (
          <details className="mt-2">
            <summary className="cursor-pointer text-sm text-fg-2">{S.s_cho_duyet_6af96613}</summary>
            <Intro book={book} view={view} />
          </details>
        ) : (
          <Intro book={book} view={view} />
        )}
      </div>

      {/* Bốn bước: hàng chữ có số/dấu tích, bước đang mở có gạch chân hổ phách như tab - không bốn thẻ viền (DESIGN 4). */}
      <ol className="mt-5 flex flex-wrap gap-x-6 border-b border-line max-sm:grid max-sm:grid-cols-2 max-sm:gap-x-4" aria-label={S.s_cac_buoc_duyet_d69dc0a2}>
        {PRECAST_STEPS.map((value, position) => {
          const Icon = STEP_ICON[value];
          const active = value === step;
          return (
            <li key={value} className="min-w-0">
              <button
                type="button"
                aria-current={active ? "step" : undefined}
                onClick={() => setStep(value)}
                className={cn(
                  // h-full: thẻ "Xong" không có dòng phụ vẫn cao bằng ba thẻ cạnh (soát 24-10 T19).
                  "touch-row -mb-px flex h-full w-full items-center gap-3 border-b-2 py-3 text-left transition-colors",
                  active ? "border-accent" : "border-transparent hover:text-fg",
                )}
              >
                {/* Biểu tượng trơn (không vòng): mực của nó thẳng mép cột chữ ở bước đầu (ink-start). Xong = dấu tích xanh, đang mở = hổ phách. */}
                <MotionRegion as="span" className={cn("grid shrink-0 place-items-center transition-colors", position < index ? "text-success" : active ? "text-accent-text" : "text-fg-3")}>
                  {position < index ? <Check className="ink-start size-4" strokeWidth={2.5} /> : <Icon className="ink-start size-4" />}
                </MotionRegion>
                <span className="min-w-0">
                  <span className={cn("block text-sm font-medium leading-tight", active ? "text-fg" : "text-fg-2")}>{STEP_TITLE[value]}</span>
                  {counts[value] && <span className="block truncate text-xs text-fg-2">{counts[value]}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>

      <section id="precast-step" tabIndex={-1} className="mt-5 outline-none" aria-label={STEP_TITLE[step]}>
        {step === "cast" && (
          <>
            <p className="max-w-3xl text-sm text-fg-2">{S.s_nghe_va_chinh_giong_cho_b5f5cadd}{people.length}{S.s_nhan_vat_noi_nhieu_nhat_a302caa8}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {people.map((person) => (
                <div key={person.name} className="flex min-w-0 flex-col gap-1">
                  <PersonRow
                    bookId={book.id}
                    person={person}
                    onPickVoice={open.onPickVoice}
                    onMerge={open.onMerge}
                    onUnmerge={open.onUnmerge}
                    onRename={open.onRename}
                    onGender={open.onGender}
                  />
                  <Reveal when={twins.has(nameKey(person.displayName)) && person.lines > 0}><div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-1 text-xs text-fg-2">
                      <span>{S.s_cung_ten_voi_nguoi_khac_trong_sach_mot_ngu_e99f281d}</span>
                      <Button size="sm" variant="ghost" onClick={() => open.onMerge(person)}>{S.s_gop_vao_6221e312}</Button>
                    </div></Reveal>
                </div>
              ))}
            </div>
            {/* Quyết xong thẻ cuối: cả nhóm khép lại, không mất cứng giữa lúc thẻ đang khép. */}
            <MotionPresence open={castCards.length > 0}>
                <h3 className="mt-6 text-sm font-medium">{S.s_may_chua_chac_0e10b540}<span className="font-normal text-fg-2">· {castCards.length}{S.s_viec_ve_nguoi_va_giong_681679b6}</span>
                </h3>
                <WorkCards {...cards} items={castCards} />
            </MotionPresence>
          </>
        )}
        {step === "names" && (
          <>
            <p className="max-w-3xl text-sm text-fg-2">
              {nameCards.length
                ? S.s_nghe_va_sua_0_cach_doc_ten_ten_kem_chac_o_bc275c71(nameCards.length)
                : S.s_xem_va_sua_cach_doc_tung_ten_o_danh_sach_d_efbb8f8e}
            </p>
            <MotionPresence open={nameCards.length > 0}><WorkCards {...cards} items={nameCards} /></MotionPresence>
            <details className="mt-6 border-t border-line">
              <summary className="touch-reach cursor-pointer text-sm font-medium text-fg-2">{S.s_cach_doc_ten_1c46e75d}</summary>
              <NameReadings bookId={book.id} />
            </details>
          </>
        )}
        {step === "lines" && (
          <>
            <p className="max-w-3xl text-sm text-fg-2">
              {lineCards.length
                ? S.s_0_cau_may_chua_chac_ai_noi_o_1_cac_chuong_b54ef45a(formatNumber(lineCount(lineCards)), range || S.s_nhung_chuong_sap_thu_969d3947)
                : view.upcoming.length
                  ? S.s_khong_co_cau_nghi_ngo_o_0_146b864d(range)
                  : S.s_da_thu_moi_chuong_52c1b8d5}{" "}{S.s_cac_chuong_sau_xem_o_viec_can_duyet_4bdcd63e}</p>
            <MotionPresence open={lineCards.length > 0}><WorkCards {...cards} items={lineCards} /></MotionPresence>
          </>
        )}
        {step === "done" && (
          <EmptyState icon={ClipboardCheck} title={S.s_xong_luot_duyet_aaf11626} className="py-10" action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button variant="ghost" size="lg" onClick={open.onClose}>{S.s_ve_danh_sach_chuong_b5fd5434}</Button>
            </div>
          }>
            {book.precast?.held
              ? S.s_da_ghi_lai_bam_thu_am_de_lam_tiep_0f63f737
              : book.running
                ? S.s_sua_nao_cung_da_ghi_lai_may_ap_o_chuong_ke_7b639271
                : S.s_sua_nao_cung_da_ghi_lai_may_ap_khi_sach_ch_eb78b798}
          </EmptyState>
        )}
      </section>

      {step !== "done" && (
        <div className="mt-6 flex flex-wrap justify-end gap-2 border-t border-line pt-4">
          <Button variant="ghost" onClick={next}>{S.s_bo_qua_buoc_nay_128392ff}</Button>
          <Button variant="primary" onClick={next}>{S.s_tiep_tuc_87a7ae88}</Button>
        </div>
      )}
    </MotionRegion>
  );
}

/** Dải mời trên trang dự án: phân tích xong, chưa thu bao nhiêu - mở màn duyệt (hay "Thu âm" khi sách đang chờ). */
export function PrecastBanner({ book, onOpen }: { book: BookSummary; onOpen: () => void }) {
  const held = Boolean(book.precast?.held);
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3 py-4">
      <ClipboardCheck className={cn("size-5 shrink-0", held ? "text-warning" : "text-accent-text")} />
      <div className="min-w-0 flex-1 text-sm">
        <div className="font-medium">{held ? S.s_phan_tich_xong_sach_dang_cho_ban_duyet_4df5357f : S.s_phan_tich_xong_duyet_truoc_khi_thu_86b704d6}</div>
        <div className="text-fg-2">{S.s_duyet_giong_ten_va_nguoi_noi_truoc_de_tran_fcbf5c99}</div>
      </div>
      {/* Chờ duyệt: nút "Thu âm" đã là nút chính ở đầu trang (ProjectScreen Actions) - dải này chỉ mời duyệt, không thêm nút thứ hai. */}
      <div className="flex gap-2">
        <Button variant={held ? "ghost" : "primary"} onClick={onOpen}>{S.s_duyet_ngay_9f97c010}</Button>
      </div>
    </div>
  );
}
