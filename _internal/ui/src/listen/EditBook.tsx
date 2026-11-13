import { Presence } from "../shared/MotionPresence";
import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { useBackLayer } from "@/shared/backStack";
import { useMotionState } from "@/shared/motion";
import * as DropdownMenu from "@/shared/DropdownMenu";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileDown, Globe, ImagePlus, EighthNote, Pencil, Shuffle, Trash2, Wrench } from "lucide-react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { toast, toastDone } from "@/shared/toast";
import { BookCover } from "@/shared/BookCover";
import { cn } from "@/shared/cn";
import { Collapse, useFold } from "@/shared/Collapse";
import { DisclosureRow } from "@/shared/DisclosureRow";
import { SectionHeading } from "@/shared/SectionHeading";
import { COVER_SEARCH_NOTE, COVER_SEARCH_TITLE, CoverSearchPanel } from "@/shared/CoverSearch";
import { canEditLayer, editBlockedNote, studioNeed, syncsToComputer } from "@/shared/capabilities";
import { formatClock } from "@/shared/format";
import { MusicLevelSlider } from "@/shared/MusicLevelSlider";
import { LEVEL_TITLE } from "@/shared/musicLevels";
import { Switch } from "@/desktop/Switch";
import { DialogActions, Button, Dialog, ChoiceRow, ContentSkeleton, InlineError } from "@/shared/ui";
import { api } from "@/studio/api";
import { MUSIC_CHANGED_EVENT } from "./musicBed";
import { OpenMusicRow } from "@/music/OpenMusicRow";
import { BrowseLibraryLink } from "@/music/BrowseLibraryLink";
import { SwapTrack } from "./MyMusic";
import { seriesOf, type ListenBook, type ListenChapter } from "./model";
import { useSource } from "./source";
import { BookReadingsSection } from "./WordReadings";
import { useFadeScroller } from "@/shared/scrollFade";

import { Reveal } from "../shared/MotionPresence";
// Sửa sách "áp ngay" ngay trên trang nghe (docs/EDITING.md): tên sách, tác giả, bìa, tên nhân vật, tên chương, nhạc nền. Cùng một bộ
// màn hình cho máy tính và điện thoại - lệnh đi tới `/api/books/<mã>/...`; máy tính là server Python, điện thoại là lõi native
// (android/localStudio.ts) trả cùng JSON. Cuốn có xưởng (dự án) ghi vào các file riêng của dự án, cuốn nhập từ file ghi vào
// lớp sửa cạnh sách - người dùng không phải biết khác biệt ấy.

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** Làm mới mọi chỗ hiện thứ vừa sửa: thư viện, trang sách, dàn nhân vật, chữ đọc theo, và trình phát nạp lại mốc nhạc. */
export function refreshAfterEdit(client: QueryClient, bookId: string): void {
  void client.invalidateQueries({ queryKey: ["listen"] });
  void client.invalidateQueries({ queryKey: ["library"] });
  void client.invalidateQueries({ queryKey: ["book", bookId] });
  void client.invalidateQueries({ queryKey: ["cast", bookId] });
}

/** Cuốn này sửa được ngay trên trang nghe không (cuốn của máy này, có xưởng hay không). */
export function canEditBook(book: Pick<ListenBook, "capabilities"> | undefined): boolean {
  return canEditLayer(book?.capabilities);
}

/** Chữ người gõ như máy chủ làm sạch (khoảng trắng gộp một dấu cách, bỏ đầu cuối): "Nguyễn  Nhật Ánh " và "Nguyễn Nhật Ánh" là một. */
function tidy(text: string): string {
  return text.trim().replace(/\s+/g, " ");
}

/** Ô "Tác giả" lưu được không: chữ gõ khác tác giả đang hiện (trống cũng là một thay đổi nếu sách đang có tác giả: bỏ tên tác giả). */
export function authorSaveable(typed: string, shown: string | undefined): boolean {
  return tidy(typed) !== tidy(shown ?? "");
}

/** Đặt tác giả của sách (lớp sửa của cuốn nhập từ file); tên trống là "không rõ tác giả". Trả tác giả đã làm sạch. */
export async function saveAuthor(bookId: string, author: string): Promise<string> {
  const saved = await api<{ author: string }>(`/api/books/${bookId}/author`, { method: "PUT", body: { author } });
  return saved.author;
}

const MAX_SIDE = 1600;

/** Ảnh bìa người dùng chọn -> data URL JPEG đã thu nhỏ (cạnh dài <= 1600): ảnh chụp 12 MB không phải đi qua cầu nối của
 *  điện thoại. Máy chủ / lõi native vẫn chuẩn hoá lại; không thu nhỏ được (trình duyệt lạ) thì gửi nguyên ảnh. */
async function imageToDataUrl(file: Blob): Promise<string> {
  const raw = () =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error ?? new Error(S.s_chua_doc_duoc_anh_ban_hay_chon_jpeg_png_ho_4d815d29));
      reader.readAsDataURL(file);
    });
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.type === "image/jpeg") return await raw();
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) return await raw();
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    return canvas.toDataURL("image/jpeg", 0.9);
  } catch {
    return raw();
  }
}

export interface MusicEditView {
  /** Cuốn là dự án Studio (không phải sách đóng gói): bật/tắt và mức là của chính dự án, đổi ở đây cũng là đổi trong Studio. */
  project?: boolean;
  /** Lời báo của máy chủ khi nhạc chưa dựng lại được (mất mạng...): lựa chọn đã lưu. */
  error?: string;
  hasMusic: boolean;
  enabled: boolean;
  levelDb: number;
  defaultLevelDb: number;
  cues: {
    key: string;
    chapterId: number;
    chapter: string;
    start: number;
    end: number;
    title: string;
    creator: string;
    silenced: boolean;
    /** Người nghe đã đổi đoạn này sang một bài trong "Nhạc của tôi". */
    pinned?: boolean;
  }[];
}

/** Lời đáp `GET /api/books/<mã>/music` của dự án Studio (`music_view` của server.py): rãnh nhạc + lựa chọn của người dùng, không có hình của sách đóng gói. */
interface ProjectMusicView {
  plan?: { enabled?: boolean; levelDb?: number; scenes?: unknown[] } | null;
  overrides?: { enabled?: boolean; levelDb?: number };
  error?: string;
}

/** Màn nhạc của cuốn dưới một hình duy nhất cho nút "Nhạc nền" và hộp "Sửa sách": sách đóng gói giữ nguyên, dự án Studio đọc `plan` / `overrides` (cùng lệnh PUT cập nhật nhạc của dự án). */
export function musicEditView(raw: MusicEditView | ProjectMusicView): MusicEditView {
  if ("hasMusic" in raw) return raw;
  const level = raw.overrides?.levelDb ?? raw.plan?.levelDb ?? -20;
  return {
    project: true,
    hasMusic: Boolean(raw.plan?.scenes?.length),
    enabled: raw.overrides?.enabled !== false,
    levelDb: level,
    defaultLevelDb: -20,
    cues: [],
    error: raw.error,
  };
}

export type MusicChange = { enabled?: boolean; levelDb?: number; silence?: Record<string, boolean>; pins?: Record<string, string | null> };

/** Nhạc nền đã gắn sẵn của cuốn (người làm sách) + cách đổi: dùng chung cho hộp "Sửa sách" và nút nhạc nền của trình phát - một lệnh
 *  PUT, một khoá nhớ, nên đổi ở đâu thì nơi kia thấy ngay. `onChanged`: việc riêng của chỗ gọi sau khi đổi xong. */
export function musicQuery(bookId: string) {
  return { queryKey: ["listen", "edit-music", bookId], queryFn: () => api<MusicEditView | ProjectMusicView>(`/api/books/${bookId}/music`), staleTime: 30_000 };
}

export function useBookMusic(bookId: string, onChanged?: () => void) {
  const client = useQueryClient();
  const key = musicQuery(bookId).queryKey;
  const view = useQuery({ ...musicQuery(bookId), select: musicEditView });
  const change = useMutation({
    scope: { id: `book-music:${bookId}` },
    mutationFn: (body: MusicChange) => api<MusicEditView | ProjectMusicView>(`/api/books/${bookId}/music`, { method: "PUT", body }),
    onSuccess: (next) => {
      client.setQueryData(key, next);
      onChanged?.();
      refreshAfterEdit(client, bookId);
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error) => toast.error(S.s_chua_chinh_duoc_nhac_nen_312d1561, { description: error.message }),
  });
  return { view, change };
}

/** Nhạc nền của cuốn nhập từ file: người làm sách đã gắn sẵn - người nghe bật/tắt, chỉnh mức, cho im lặng từng đoạn, và đổi một đoạn
 *  sang bài trong "Nhạc của tôi" (bài ấy đi cùng file sách khi lưu). */
export function MusicSection({ book }: { book: ListenBook }) {
  const scrollFade = useFadeScroller<HTMLUListElement>();
  const [swapping, , setSwapping] = useMotionState<string | null>(null); // MotionRegion giữ chuyển động cục bộ khi đóng "Đổi bài".
  const swapBox = useRef<HTMLDivElement>(null);
  const swapButton = useRef<HTMLButtonElement>(null);
  useBackLayer(swapping !== null, () => setSwapping(null), swapBox, swapButton);
  const { view, change } = useBookMusic(book.id, () => setSwapping(null));
  const { data, isLoading } = view;
  if (view.isError && !data) return <MotionRegion fadeThrough><InlineError message={S.s_ban_hay_thu_tai_lai_nhac_nen_cua_cuon_nay_b4336281} onRetry={() => void view.refetch()} /></MotionRegion>;
  if (isLoading || !data) return <MotionRegion fadeThrough><ContentSkeleton label={S.s_dang_tai_nhac_nen_0b8c4795} /></MotionRegion>;
  if (!data.hasMusic) {
    return <MotionRegion as="p" className="text-sm text-fg-2">{S.s_nguoi_lam_sach_khong_gan_nhac_nen_cho_cuon_80c1a983}</MotionRegion>;
  }
  const choosing = change.isPending ? (Object.values(change.variables?.pins ?? {}).find((link): link is string => !!link) ?? null) : null;
  return (
    <MotionRegion as="div" elementRef={swapBox} className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        {/* Công tắc nói trạng thái ("Bật" / "Tắt"); tên mục "Nhạc nền" đã ở ngay trên, không lặp lại. */}
        <div className="flex h-9 items-center gap-3 text-sm">
          <Switch id={`music-enabled-${book.id}`} label={S.s_nhac_nen_271fb292} checked={data.enabled} disabled={change.isPending} onCheckedChange={(enabled) => change.mutate({ enabled })} />
          <label htmlFor={`music-enabled-${book.id}`}>{data.enabled ? S.s_bat_f26cbc4a : S.s_tat_3286064e}</label>
        </div>
        <div className="w-full max-w-72 text-sm">
          <span className="block text-fg-2">{LEVEL_TITLE}</span>
          <MusicLevelSlider value={data.levelDb} saving={change.isPending} onChange={(levelDb) => change.mutate({ levelDb })} className="mt-1" />
        </div>
      </div>
      <ul ref={scrollFade.ref} style={scrollFade.style} className={cn("max-h-72 divide-y divide-line overflow-y-auto", !data.enabled && "opacity-50")}>
        {data.cues.map((cue) => (
          <li key={cue.key}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
              <div className="min-w-[9rem] flex-1">
                {/* Đoạn người nghe cho im: nói thẳng (như tab Nhạc của dự án), không gạch ngang tên - gạch ngang đọc như lỗi. */}
                <div className={cn("truncate text-sm", cue.silenced && "text-fg-2")}>{cue.silenced ? S.s_im_lang_ban_chon_356a628b : cue.title || S.s_nhac_nen_271fb292}</div>
                <div className="truncate text-xs text-fg-2">
                  {cue.chapter} · {formatClock(cue.start)} – {formatClock(cue.end)}
                  {cue.creator ? ` · ${cue.creator}` : ""}
                  {cue.pinned ? S.s_bai_cua_ban_c8ffb389 : ""}
                </div>
              </div>
              <span className="flex shrink-0 gap-1">
                <Reveal when={cue.pinned}><Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ pins: { [cue.key]: null } })}>{S.s_ve_bai_goc_dc6a21f6}</Button></Reveal>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={Shuffle}
                  aria-expanded={swapping === cue.key}
                  disabled={change.isPending}
                  onClick={(event) => { swapButton.current = event.currentTarget; setSwapping(swapping === cue.key ? null : cue.key); }}
                >{S.s_doi_bai_7b81488f}</Button>
                <Button size="sm" variant="ghost" disabled={change.isPending} onClick={() => change.mutate({ silence: { [cue.key]: !cue.silenced } })}>
                  {/* Bề ngang theo chữ dài hơn trong hai chữ: "Đổi bài" đứng một cột ở mọi dòng. */}
                  <span className="grid">
                    <span className="col-start-1 row-start-1">{cue.silenced ? S.s_co_nhac_f514e0fa : S.s_im_lang_1a012238}</span>
                    <span aria-hidden className="invisible col-start-1 row-start-1">{cue.silenced ? S.s_im_lang_1a012238 : S.s_co_nhac_f514e0fa}</span>
                  </span>
                </Button>
              </span>
            </div>
            {<Presence>{swapping === cue.key && (
              <SwapTrack
                bookId={book.id}
                cueKey={cue.key}
                busy={change.isPending}
                choosing={choosing}
                onChoose={(link) => change.mutate({ pins: { [cue.key]: link }, ...(cue.silenced ? { silence: { [cue.key]: false } } : {}) })}
              />
            )}</Presence>}
            {/* Cuối "Đổi bài": cả kho nhạc ở chế độ chọn cho đúng đoạn này ("Dùng" ghim bài như "Chọn" ở trên). */}
            {<Presence>{swapping === cue.key && (
              <BrowseLibraryLink bookId={book.id} scene={cue.key} className="px-3" />
            )}</Presence>}
          </li>
        ))}
      </ul>
      <OpenMusicRow />
    </MotionRegion>
  );
}

/** `fold`: mục ít dùng gập lại (khoá nhớ gấp / mở) - hộp năm mục dài hơn một màn điện thoại (a120). */
function Section({ title, hint, children, fold }: { title: string; hint?: string; children?: ReactNode; fold?: string }) {
  if (fold) return <FoldedSection title={title} hint={hint} storageKey={fold}>{children}</FoldedSection>;
  return (
    <section className="border-t border-line pt-4 first:border-t-0 first:pt-0">
      <SectionHeading as="h3">{title}</SectionHeading>
      <Reveal when={hint}><p className="mb-2 text-xs text-fg-2">{hint}</p></Reveal>
      <Reveal when={children}><div className={hint ? undefined : "mt-2"}>{children}</div></Reveal>
    </section>
  );
}

function FoldedSection({ title, hint, children, storageKey }: { title: string; hint?: string; children?: ReactNode; storageKey: string }) {
  const [open, setOpen] = useFold(storageKey);
  const id = useId();
  return (
    <section className="border-t border-line pt-2 first:border-t-0 first:pt-0">
      <h3 className="m-0">
        <DisclosureRow section title={title} expanded={open} controls={id} onClick={() => setOpen(!open)} />
      </h3>
      <Collapse open={open} id={id}>
        <Reveal when={hint}><p className="mb-2 text-xs text-fg-2">{hint}</p></Reveal>
        <Reveal when={children}><div className={hint ? undefined : "mt-2"}>{children}</div></Reveal>
      </Collapse>
    </section>
  );
}

/** Hộp "Sửa sách": tên, tác giả, bìa, nhạc nền, bỏ mọi thay đổi. Tên nhân vật và tên chương sửa ngay ở tab Nhân vật / dòng chương. */
export function EditBookDialog({
  book,
  open,
  onOpenChange,
  onOpenStudio,
  computer,
}: {
  book: ListenBook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Máy tính, cuốn có xưởng: nhạc nền chỉnh đầy đủ ở tab Nhạc nền của Studio. */
  onOpenStudio?: () => void;
  /** Studio từ xa: tên máy tính đang giữ sách - sửa áp lên sách ở đó. */
  computer?: string;
}) {
  const scrollFade = useFadeScroller<HTMLDivElement>();
  const client = useQueryClient();
  const [title, setTitle] = useState(book.title);
  const [author, setAuthor] = useState(book.author ?? "");
  const file = useRef<HTMLInputElement | null>(null);
  const [confirmRevert, setConfirmRevert] = useState(false);
  const revertBox = useRef<HTMLDivElement>(null);
  const revertButton = useRef<HTMLButtonElement>(null);
  useBackLayer(open && confirmRevert, () => setConfirmRevert(false), revertBox, revertButton);
  const [searching, setSearching] = useState(false);
  const searchBack = useRef<HTMLButtonElement>(null);
  const searchOpener = useRef<HTMLButtonElement>(null);
  useBackLayer(open && searching, () => setSearching(false), searchBack, searchOpener);
  // Mở hộp: nạp lại cả hai ô. Lưu một ô (hộp ở nguyên) chỉ nạp ô ấy - chữ gõ dở ở ô kia không mất (soát UX a17).
  useEffect(() => {
    if (open) {
      setTitle(book.title);
      setAuthor(book.author ?? "");
      setConfirmRevert(false);
      setSearching(false);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setTitle(book.title), [book.title]);
  useEffect(() => setAuthor(book.author ?? ""), [book.author]);
  const workshop = Boolean(book.capabilities?.workshop);
  const done = (message: string) => {
    refreshAfterEdit(client, book.id);
    toast.success(message);
  };
  const rename = useMutation({
    mutationFn: (next: string) => api(`/api/books/${book.id}/title`, { method: "PUT", body: { title: next } }),
    // Hộp ở nguyên: toast báo đã lưu, ô còn lại giữ chữ đang gõ (trước đây lưu là đóng hộp - mất chữ gõ dở ở ô kia).
    onSuccess: () => done(S.s_da_doi_ten_sach_d9618322),
    onError: (error: Error) => toast.error(S.s_chua_doi_duoc_ten_sach_d845e696, { description: error.message }),
  });
  const changeAuthor = useMutation({
    mutationFn: (next: string) => saveAuthor(book.id, next),
    onSuccess: (saved) => done(saved ? S.s_da_doi_tac_gia_cc6c70a5 : S.s_da_bo_ten_tac_gia_538a5212),
    onError: (error: Error) => toast.error(S.s_chua_doi_duoc_tac_gia_32e393fb, { description: error.message }),
  });
  const setCover = useMutation({
    mutationFn: async (picked: Blob) => api(`/api/books/${book.id}/cover`, { method: "PUT", body: { image: await imageToDataUrl(picked) } }),
    onSuccess: () => done(S.s_da_dat_anh_bia_90470364),
    onError: (error: Error) => toast.error(S.s_chua_dat_duoc_anh_bia_a4afb9fa, { description: error.message }),
  });
  const removeCover = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/cover`, { method: "DELETE" }),
    onSuccess: () => done(S.s_da_bo_anh_bia_sach_dung_bia_ve_tu_ten_f562bcab),
    onError: (error: Error) => toast.error(S.s_chua_bo_duoc_anh_bia_a4173b5d, { description: error.message }),
  });
  const revert = useMutation({
    mutationFn: () => api(`/api/books/${book.id}/edits`, { method: "DELETE" }),
    onSuccess: () => {
      setConfirmRevert(false);
      done(S.s_da_bo_moi_thay_doi_sach_nhu_nguoi_lam_sach_eecea191);
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: book.id }));
    },
    onError: (error: Error) => toast.error(S.s_chua_bo_duoc_thay_doi_e73f2d58, { description: error.message }),
  });
  const [choosingCover, setChoosingCover] = useState(false); // ảnh bìa mạng đã chọn đang về
  const busy = rename.isPending || changeAuthor.isPending || setCover.isPending || removeCover.isPending || choosingCover;
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-[560px]"
      title={searching ? COVER_SEARCH_TITLE : S.s_sua_sach_79fb71d2}
      // Không lời dẫn chung đầu hộp (điện thoại cũng không có): phần sửa chờ gửi tự nói ở dòng tình trạng dưới tên sách (SendEdits.tsx). Riêng
      // Studio từ xa nói rõ là đang sửa sách trên máy tính.
      description={
        searching
          ? COVER_SEARCH_NOTE
          : computer
          ? S.s_doi_co_hieu_luc_ngay_tren_may_tinh_0_audio_1381413a(computer)
          : undefined
      }
    >{/* Tìm bìa là MỘT BƯỚC của hộp này (trượt sang, có "Quay lại", Back cũng về), không phải hộp thứ hai đè lên (audit140 V9). */}
    <MotionRegion motionKey={searching}>{searching ? (
      <div>
        <button ref={searchBack} type="button" onClick={() => setSearching(false)} className="touch-hit touch-row mb-3 inline-flex items-center gap-2 text-sm text-fg-2 hover:text-fg">
          <ArrowLeft className="ink-start size-4" />{S.s_sua_sach_44914329}</button>
        <CoverSearchPanel
          bookId={book.id}
          defaultQuery={seriesOf(book.title).series || book.title}
          active={open && searching}
          onClose={() => setSearching(false)}
          onChosen={() => refreshAfterEdit(client, book.id)}
          onBusy={setChoosingCover}
          onChooseFile={() => file.current?.click()}
        />
      </div>
    ) : (
      <div ref={scrollFade.ref} style={scrollFade.style} className="focus-scroll max-h-[68vh] space-y-4 overflow-y-auto pr-1">
        <Section title={S.s_ten_sach_d54846eb}>
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (title.trim() && title.trim() !== book.title) rename.mutate(title);
            }}
          >
            <input
              data-autofocus
              value={title}
              maxLength={160}
              aria-label={S.s_ten_sach_d54846eb}
              onChange={(event) => setTitle(event.target.value)}
              className="touch-box h-[40px] min-w-0 flex-1 rounded-control border border-line bg-bg px-3 text-sm outline-none focus:border-focus"
            />
            <Button type="submit" variant="primary" className="touch-box h-10 min-h-10 max-sm:min-h-[48px] pointer-coarse:min-h-[48px]" loading={rename.isPending} disabled={!title.trim() || title.trim() === book.title}>{S.s_luu_ten_0b3ef54a}</Button>
          </form>
        </Section>
        {/* Chỉ sách chữ (nhập từ file): sách Studio không có chỗ áp tác giả, sửa ở máy khác rồi gửi về là mất (fold_edits bỏ qua). */}
        {<Presence>{book.stage === "text" && !workshop && (
          <Section title={S.s_tac_gia_0ec4731b}>
            <form
              className="flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (authorSaveable(author, book.author)) changeAuthor.mutate(author);
              }}
            >
              <input
                value={author}
                maxLength={160}
                aria-label={S.s_tac_gia_0ec4731b}
                placeholder={S.s_khong_ro_tac_gia_baaa8118}
                onChange={(event) => setAuthor(event.target.value)}
                className="touch-box h-[40px] min-w-0 flex-1 rounded-control border border-line bg-bg px-3 text-sm outline-none focus:border-focus"
              />
              <Button type="submit" variant="primary" className="touch-box h-10 min-h-10 max-sm:min-h-[48px] pointer-coarse:min-h-[48px]" loading={changeAuthor.isPending} disabled={!authorSaveable(author, book.author)}>{S.s_luu_tac_gia_cd5c8008}</Button>
            </form>
          </Section>
        )}</Presence>}
        <Section title={S.s_anh_bia_f224644d}>
          {/* flex-wrap: ở 375 px cột nút (rộng ~190 px) không vừa cạnh bìa 112 px - xuống dưới bìa thay vì tràn khỏi hộp (soát UX a17). */}
          <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
            <BookCover title={book.title} part={book.series?.part} size="lg" image={book.cover} className="w-28 shrink-0" />
            {/* Nút chữ xếp chồng canh trái chung một mép (icon thẳng hàng); kéo giãn thì chữ canh giữa từng nút, lệch nhau (soát 25-10). */}
            <div className="flex min-w-0 max-w-full flex-col items-start gap-1">
              <Button variant="ghost" className="justify-start text-left" icon={ImagePlus} disabled={busy} onClick={() => file.current?.click()}>
                {book.cover ? S.s_doi_anh_bia_7889ff91 : S.s_chon_anh_bia_207ac182}
              </Button>
              <Button ref={searchOpener} variant="ghost" className="justify-start text-left" icon={Globe} disabled={busy} onClick={() => setSearching(true)}>{S.s_tim_bia_34025664}</Button>
              <Reveal when={book.cover}><Button variant="ghost" className="justify-start text-left" icon={Trash2} disabled={busy} onClick={() => removeCover.mutate()}>{S.s_bo_anh_bia_696c6692}</Button></Reveal>
              {<Presence>{setCover.isPending && (
                <ContentSkeleton count={1} label={S.s_dang_dat_anh_bia_f4a60e45} />
              )}</Presence>}
            </div>
          </div>
        </Section>
        {<Presence>{book.stage !== "text" && (
        <Section title={S.s_nhac_nen_271fb292} fold="edit-book.music">
          {workshop ? (
            <div className="flex flex-wrap items-center gap-3 text-sm text-fg-2">
              <span>{S.s_cuon_nay_co_xuong_nhac_nen_chinh_day_du_ch_b296f56d}</span>
              <Reveal when={onOpenStudio}><Button size="sm" variant="ghost" icon={EighthNote} onClick={onOpenStudio}>{S.s_mo_tab_nhac_nen_117e60f2}</Button></Reveal>
            </div>
          ) : (
            <MusicSection book={book} />
          )}
        </Section>
        )}</Presence>}
        <Section
          title={book.stage === "text" ? S.s_ten_chuong_9edb6c28 : S.s_ten_rieng_8a9cd50f}
          hint={book.stage === "text" ? S.s_bam_o_dong_chuong_de_doi_ten_chuong_d2fb9984 : S.s_bam_o_dong_chuong_de_doi_ten_chuong_o_tab_733e1523}
        />
        {<Presence>{book.stage === "text" && !workshop && (
          <Section title={S.s_cach_doc_ten_1c46e75d} hint={S.s_day_cach_doc_tu_thuong_la_ten_rieng_chu_gi_69023eb0} fold="edit-book.readings">
            <BookReadingsSection bookId={book.id} />
          </Section>
        )}</Presence>}
        {<Presence>{!workshop && (book.edits ?? 0) > 0 && (
          <Section title={S.s_bo_moi_thay_doi_0_af6c6828(book.edits)} hint={S.s_sach_tro_ve_dung_nhu_nguoi_lam_sach_da_don_f3a48d43}>
            {confirmRevert ? (
              <div ref={revertBox} className="flex gap-2">
                <Button variant="danger" loading={revert.isPending} onClick={() => revert.mutate()}>{S.s_bo_het_thay_doi_b55603a1}</Button>
                <Button variant="ghost" onClick={() => setConfirmRevert(false)}>{S.s_thoi_e68f9e88}</Button>
              </div>
            ) : (
              <Button ref={revertButton} variant="ghost" className="-ml-4" onClick={() => setConfirmRevert(true)}>{S.s_bo_moi_thay_doi_ad999cde}</Button>
            )}
          </Section>
        )}</Presence>}
      </div>
    )}</MotionRegion>
    <input
      ref={file}
      type="file"
      accept="image/png,image/jpeg,image/webp,image/gif,image/bmp"
      className="hidden"
      onChange={(event) => {
        const picked = event.target.files?.[0];
        event.target.value = "";
        if (picked) setCover.mutate(picked);
      }}
    /></Dialog>
  );
}

/** Tên chương đang hiện trên dòng chương (nhãn + tên phụ nếu có). */
export function chapterShownName(chapter: Pick<ListenChapter, "title" | "fullTitle"> | null): string {
  return chapter ? chapter.fullTitle || chapter.title : "";
}

/** Đổi tên một chương: nhãn ("Chương 12") và tên ("Hồi kết"); "Về tên gốc" trả lại tên của người làm sách. Sách chữ (nhập từ file) chỉ có
 *  MỘT tên - dòng đầu chương, không tách nhãn / tên: một ô "Tên chương" điền sẵn tên đang thấy, lưu thì tên mới thay hẳn (cùng lệnh PUT,
 *  nhãn = tên mới, tên phụ trống). Sách Studio giữ hai ô. */
export function RenameChapterDialog({ book, chapter, onClose }: { book: ListenBook; chapter: ListenChapter | null; onClose: () => void }) {
  const dialogForm1 = useId();
  const client = useQueryClient();
  const single = book.stage === "text" && !book.capabilities?.workshop;
  const [label, setLabel] = useState("");
  const [name, setName] = useState("");
  useEffect(() => {
    setLabel(single ? chapterShownName(chapter) : (chapter?.title ?? ""));
    setName(single ? "" : (chapter?.subtitle ?? ""));
  }, [chapter, single]);
  const save = useMutation({
    mutationFn: (body: { title?: string; subtitle?: string; revert?: boolean }) =>
      api<{ fullTitle: string }>(`/api/books/${book.id}/chapters/${chapter?.id}/title`, { method: "PUT", body }),
    onSuccess: (answer) => {
      refreshAfterEdit(client, book.id);
      toast.success(S.s_da_doi_ten_chuong_0_e09362d6(answer.fullTitle));
      onClose();
    },
    onError: (error: Error) => toast.error(S.s_chua_doi_duoc_ten_chuong_1ff36fe9, { description: error.message }),
  });
  return (
    <Dialog footer={<DialogActions>
          <Button type="button" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ revert: true })}>{S.s_ve_ten_goc_643cd2e0}</Button>
          <Button type="button" variant="ghost" onClick={onClose}>{S.s_thoi_e68f9e88}</Button>
          <Button type="submit" form={dialogForm1} variant="primary" loading={save.isPending} disabled={!label.trim()}>{S.s_luu_e91f26c0}</Button>
        </DialogActions>}
      open={chapter !== null}
      onOpenChange={(open) => !open && onClose()}
      width="max-w-md"
      title={S.s_ten_chuong_9edb6c28}
    >
      <form id={dialogForm1}
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (label.trim()) save.mutate({ title: label, subtitle: name });
        }}
      >
        <label className="block text-sm">
          <span className="text-fg-2">{single ? S.s_ten_chuong_9edb6c28 : S.s_nhan_58861f44}</span>
          <input
            data-autofocus
            value={label}
            maxLength={160}
            onChange={(event) => setLabel(event.target.value)}
            className="mt-1 h-9 w-full rounded-control border border-line bg-bg px-3 text-sm outline-none focus-visible:border-focus"
          />
        </label>
        <Reveal when={!single}><label className="block text-sm">
            <span className="text-fg-2">{S.s_ten_c8b17259}</span>
            <input
              value={name}
              maxLength={160}
              onChange={(event) => setName(event.target.value)}
              className="mt-1 h-9 w-full rounded-control border border-line bg-bg px-3 text-sm outline-none focus-visible:border-focus"
            />
          </label></Reveal>

      </form>
    </Dialog>
  );
}

/** "Lưu": đóng cuốn (kèm thay đổi của người nghe) thành file mới, GIỮ loại file cuốn đã đến (`.abookproj` mang theo xưởng của nó,
 *  `.abook` thì không). Máy tính ghi vào thư mục xuất (hay thư mục đã chọn), điện thoại hỏi chỗ lưu. Trả hàm lưu và trạng thái bận. */
export function useSaveBook(book: ListenBook) {
  const source = useSource();
  const [busy, setBusy] = useState(false);
  /** Trả true khi đã lưu thành file; huỷ hộp chọn chỗ lưu hay lỗi thì false (hộp "Lưu thành" giữ nguyên lựa chọn để thử lại). */
  const save = async (options?: { folder?: string; as?: "abook" | "abookproj"; ask?: boolean }): Promise<boolean> => {
    if (!source.saveBook) return false;
    setBusy(true);
    try {
      const result = await source.saveBook(book.id, options);
      if (!result.saved) return false;
      const folder = result.folder;
      // Không có thay đổi nào vẫn lưu được, nhưng file giống hệt bản gốc: nói điều đó thành cảnh báo cùng dòng.
      toastDone(S.s_da_luu_file_sach_baab68d2, result.edits ? undefined : S.s_chua_co_thay_doi_nao_file_giong_ban_goc_f109003f, {
        duration: 8000,
        action: folder
          ? { label: S.s_mo_thu_muc_4bf5b127, onClick: () => void api("/api/reveal-export", { method: "POST", body: { folder } }).catch(() => undefined) }
          : undefined,
      });
      return true;
    } catch (error) {
      toast.error(S.s_chua_luu_duoc_file_sach_964ff92c, { description: (error as Error).message });
      return false;
    } finally {
      setBusy(false);
    }
  };
  return { save, busy, available: Boolean(source.saveBook) };
}

/** "Chia sẻ…" (điện thoại): gửi file sách của cuốn, kèm thay đổi của người nghe, qua bảng chia sẻ của hệ thống. */
export function useShareBook(book: ListenBook) {
  const source = useSource();
  const [busy, setBusy] = useState(false);
  const share = async () => {
    if (!source.shareBook) return;
    setBusy(true);
    try {
      await source.shareBook(book.id);
    } catch (error) {
      toast.error(S.s_chua_chia_se_duoc_sach_9b8501da, { description: (error as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return { share, busy, available: Boolean(source.shareBook) };
}

type SaveKind = "abook" | "abookproj";

/** "Lưu thành…": chọn loại file. `.abookproj` mang cả xưởng nếu cuốn đến từ một file dự án; không thì là file "chờ dựng xưởng"
 *  (chỉ phần nghe + thay đổi của bạn, máy có Studio mời dựng xưởng khi mở). */
export function SaveAsDialog({
  book,
  open,
  onOpenChange,
  pickFolder,
}: {
  book: ListenBook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Máy tính trong cửa sổ app: chọn thư mục lưu (hộp thoại của Windows). */
  pickFolder?: () => Promise<string | null>;
}) {
  const { save, busy } = useSaveBook(book);
  const [kind, setKind] = useMotionState<SaveKind>(book.projectFile ? "abookproj" : "abook");
  const [folder, setFolder] = useState<string | null>(null);
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>{S.s_thoi_e68f9e88}</Button>
        <Button
          variant="primary"
          icon={FileDown}
          loading={busy}
          onClick={() => void save({ ...(folder ? { folder } : {}), as: kind, ask: true }).then((saved) => saved && onOpenChange(false))}
        >{S.s_luu_e91f26c0}</Button>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-md"
      title={S.s_luu_thanh_13374e92}
      description={S.s_luu_cuon_nay_kem_nhung_thay_doi_cua_ban_th_ab80dd34}
    >
      <ChoiceRow<SaveKind>
        value={kind}
        onChange={setKind}
        label={S.s_loai_file_74f0a115}
        options={[
          { value: "abook", label: S.s_sach_nghe_abook_cb8e508e },
          { value: "abookproj", label: S.s_du_an_abookproj_71e42c40 },
        ]}
      />
      {kind === "abookproj" ? (
        <p className="mt-3 text-sm text-fg-2">
          {book.projectFile?.workshop === "present"
            ? S.s_ca_du_an_kem_thay_doi_cua_ban_mo_bang_stud_f33ca39c
            : S.s_chi_co_phan_nghe_va_thay_doi_cua_ban_studi_09cd637e}
        </p>
      ) : (
        <p className="mt-3 text-sm text-fg-2">{S.s_sach_nghe_mo_duoc_bang_abook_tren_may_tinh_ef9eba65}{book.wishes ? S.s_cung_0_viec_dang_cho_may_lam_sach_chua_lam_4b0db6d4(book.wishes) : ""}.
        </p>
      )}
      {<Presence>{pickFolder && (
        <div className="mt-3 flex items-center gap-2 text-sm">
          <Button variant="ghost" size="sm" onClick={() => void pickFolder().then((picked) => picked && setFolder(picked))}>{S.s_chon_thu_muc_1fe47e38}</Button>
          <MotionRegion as="span" motionKey={folder ?? ""} className="min-w-0 truncate text-fg-2">{folder ?? S.s_mac_dinh_thu_muc_da_xuat_65fabfd2}</MotionRegion>
        </div>
      )}</Presence>}
      <Reveal when={pickFolder}><p className="mt-2 text-xs text-fg-3">{S.s_da_co_file_cung_ten_trong_thu_muc_ay_thi_f_ca6cb2a9}</p></Reveal>

    </Dialog>
  );
}

/** Việc cần Studio vẫn hiện trong menu, mờ đi, nói rõ thiếu gì - không giấu (docs/EDITING.md: "explain, never hide"). */
export function StudioOnlyItem({ book }: { book: ListenBook }) {
  const need = studioNeed(book.capabilities);
  if (!need || book.stage === "text") return null; // sách chỉ có chữ chưa có giọng nào để đổi (có "Làm sách nói từ cuốn này")
  const syncs = syncsToComputer(book.capabilities);
  return (
    <DropdownMenu.Item disabled className={cn(MENU_ITEM, "h-auto items-start py-2 data-[disabled]:opacity-60")}>
      <Wrench className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{S.s_giong_va_loi_doc_450320f6}</span>
        <span className="block text-xs text-fg-3">{syncs ? S.s_lam_o_studio_tren_may_tinh_c89f87a5 : need.charAt(0).toUpperCase() + need.slice(1)}</span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Cuốn không sửa được ở đây (máy tính, cuốn của điện thoại chia sẻ): mục sửa vẫn hiện, mờ đi, nói vì sao - không giấu. */
export function EditBlockedItem({ book }: { book: ListenBook }) {
  const note = editBlockedNote(book.capabilities);
  if (!note) return null;
  return (
    <DropdownMenu.Item disabled className={cn(MENU_ITEM, "h-auto items-start py-2 data-[disabled]:opacity-60")}>
      <Pencil className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{S.s_sua_thong_tin_17e4a8a6}</span>
        <span className="block text-xs text-fg-3">{S.s_sua_o_may_goc_1a65caf0}</span>
      </span>
    </DropdownMenu.Item>
  );
}
