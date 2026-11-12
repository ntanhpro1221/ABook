import * as DropdownMenu from "@/shared/DropdownMenu";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, CircleAlert, Download, Loader2, Music2, Play, Search, Square, X } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "../shared/toast";
import { useBookMusic } from "../listen/EditBook";
import { MyMusicSection } from "../listen/MyMusic";
import { cn } from "../shared/cn";
import { DotJoin } from "../shared/DotJoin";
import { formatClock, formatSize } from "../shared/format";
import { MotionPresence } from "../shared/MotionPresence";
import { ScreenHeader } from "../shared/ScreenHeader";
import { S } from "../shared/strings.generated";
import { Button, ContentSkeleton, EmptyState, IconButton, InlineError, SelectionMark, Tabs, TabsContent, TabsList, TabsPanels, TabsTrigger } from "../shared/ui";
import { Windowed } from "../shared/Windowed";
import { api } from "../studio/api";
import {
  filtering, LENGTH_OPTIONS, loadOf, NO_FILTERS, TEMPO_OPTIONS, useDownloads, useLibrary, useLibraryMeta, useSaveTracks,
  type DownloadState, type LibraryFilters, type LibraryTrack,
} from "./library";
import { useLibraryPreview, type LibraryPreview } from "./preview";
import { TrackSheet } from "./TrackSheet";

/** Màn "Nhạc" (đích cấp cao nhất, docs/DESIGN.md mục Nhạc): "Đã lưu" (bài đã lưu + Nhạc của tôi) | "Kho nhạc" (cả danh mục: tìm, lọc,
 *  nghe thử, tải về). `?pick=<mã sách>&scene=<khoá đoạn>`: CHẾ ĐỘ CHỌN mở từ "Đổi bài" của một đoạn - mỗi bài có nút "Dùng", chọn xong
 *  ghim bài cho đoạn ấy (cùng đường lưu với "Đổi bài": PUT /api/books/<mã>/music {pins}) rồi quay lại. */
export function MusicScreen() {
  const [params] = useSearchParams();
  const pickBook = params.get("pick");
  const pickScene = params.get("scene");
  const picking = pickBook && pickScene ? { book: pickBook, scene: pickScene } : null;
  const [tab, setTab] = useState<"saved" | "library">(picking || params.get("tab") === "library" ? "library" : "saved");
  const preview = useLibraryPreview();
  const navigate = useNavigate();
  return (
    <div className="page-x mx-auto max-w-[1180px] pb-24">
      <ScreenHeader
        title={picking ? S.s_chon_bai_cho_doan_840afc40 : S.s_nhac_0e4413e9}
        back={picking ? { label: S.s_quay_lai_6d793582, onClick: () => navigate(-1) } : undefined}
      />
      {picking ? (
        <div className="mt-6"><PickerLibrary preview={preview} picking={picking} /></div>
      ) : (
        <Tabs value={tab} onValueChange={(value) => setTab(value as "saved" | "library")} className="mt-6">
          <TabsList label={S.s_nhac_0e4413e9}>
            <TabsTrigger value="saved">{S.s_da_luu_6379aeba}</TabsTrigger>
            <TabsTrigger value="library">{S.s_kho_nhac_94affa81}</TabsTrigger>
          </TabsList>
          <TabsPanels value={tab} className="mt-6">
            <TabsContent value="saved"><Saved preview={preview} onBrowse={() => setTab("library")} /></TabsContent>
            <TabsContent value="library"><Library preview={preview} /></TabsContent>
          </TabsPanels>
        </Tabs>
      )}
      <PreviewBar preview={preview} />
    </div>
  );
}

/** Thanh nhỏ "Đang nghe thử · tên · ■" ở đáy màn trong lúc nghe thử. */
export function PreviewBar({ preview }: { preview: LibraryPreview }) {
  const playing = preview.playing;
  return (
    <MotionPresence open={playing !== null} className="sticky bottom-3 z-10 mt-4">
      <div role="status" className="mx-auto flex max-w-[560px] items-center gap-3 rounded-cover border border-line bg-panel px-4 py-2 shadow-float">
        <Music2 aria-hidden className="size-4 shrink-0 text-accent-text" />
        <p className="min-w-0 flex-1 truncate text-sm">
          <span className="text-fg-2">{S.s_dang_nghe_thu_f1fb4cba}</span>
          {playing?.title ? <span className="font-medium"> · {playing.title}</span> : null}
        </p>
        <IconButton size="sm" label={S.s_dung_nghe_thu_41a2925b} icon={Square} onClick={preview.stop} />
      </div>
    </MotionPresence>
  );
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine !== false);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return online;
}

function Saved({ preview, onBrowse }: { preview: LibraryPreview; onBrowse: () => void }) {
  const { data, isLoading, error, refetch } = useLibrary(NO_FILTERS, true);
  const [open, setOpen] = useState<string | null>(null);
  const online = useOnline();
  const { data: downloads } = useDownloads();
  const { data: meta } = useLibraryMeta();
  return (
    <div className="space-y-10">
      <section aria-label={S.s_da_luu_6379aeba} className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          {data && data.saved.count > 0 && <p className="text-sm text-fg-2">{S.s_da_tai_0_bai_1_3cac202f(data.saved.count, formatSize(data.saved.bytes))}</p>}
        </div>
        {isLoading ? (
          <ContentSkeleton />
        ) : error && !data ? (
          <InlineError message={S.s_chua_tai_duoc_kho_nhac_9577b7c7} onRetry={() => void refetch()} />
        ) : data?.tracks.length ? (
          <ul aria-label={S.s_da_luu_6379aeba}>
            {data.tracks.map((track) => (
              <TrackRow key={track.link} track={track} preview={preview} downloads={downloads} online={online} styles={meta?.styles} onOpen={setOpen} />
            ))}
          </ul>
        ) : (
          <EmptyState icon={Music2} title={S.s_chua_luu_bai_nao_6e7558df} className="py-6"
            action={<Button variant="primary" onClick={onBrowse}>{S.s_kho_nhac_94affa81}</Button>}>{S.s_bai_da_tai_nghe_duoc_khi_khong_co_mang_ca12f3db}</EmptyState>
        )}
      </section>
      {/* "Nhạc của tôi" (nhạc tự nhập) là một phần của "Đã lưu": cùng thành phần trước đây nằm ở Cài đặt (gộp làm một, không bản sao). */}
      <MyMusicSection />
      <TrackSheet link={open} onClose={() => setOpen(null)} preview={preview} />
    </div>
  );
}

/** Kho nhạc ở chế độ chọn cho một đoạn: "Dùng" ghim bài cho đoạn qua đúng đường của "Đổi bài" (useBookMusic), "Không tự chọn bài này" =
 *  bỏ bài cho cuốn này (cơ chế "Bài đã bỏ" sẵn có của tab Nhạc). */
function PickerLibrary({ preview, picking }: { preview: LibraryPreview; picking: { book: string; scene: string } }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [closeSheet, setCloseSheet] = useState(0);
  const { change } = useBookMusic(picking.book, () => {
    toast.success(S.s_da_chon_bai_cho_doan_nay_774deab2);
    setCloseSheet((value) => value + 1);
    navigate(-1);
  });
  const ban = (link: string) => {
    void api(`/api/books/${picking.book}/music`, { method: "PUT", body: { ban: [link] } })
      .then(() => {
        void client.invalidateQueries({ queryKey: ["music-alternatives", picking.book] });
        toast(S.s_khong_tu_chon_bai_nay_ab3af35f);
      })
      .catch((problem: Error) => toast.error(problem.message));
  };
  return <Library key={closeSheet} preview={preview} use={(link) => change.mutate({ pins: { [picking.scene]: link } })} ban={ban} busy={change.isPending} />;
}

function Library({ preview, use, ban, busy }: { preview: LibraryPreview; use?: (link: string) => void; ban?: (link: string) => void; busy?: boolean }) {
  const [params] = useSearchParams();
  const [filters, setFilters] = useState<LibraryFilters>(NO_FILTERS);
  const [text, setText] = useState(() => params.get("q") ?? ""); // "Xem trong kho" từ bài đang phát: tìm sẵn tên bài
  const query = useDeferredValue(text);
  const effective = useMemo(() => ({ ...filters, q: query }), [filters, query]);
  const { data, isLoading, error, refetch, isFetching } = useLibrary(effective);
  const { data: meta } = useLibraryMeta();
  const { data: downloads } = useDownloads();
  const { save } = useSaveTracks();
  const [open, setOpen] = useState<string | null>(null);
  const online = useOnline();
  const set = (patch: Partial<LibraryFilters>) => setFilters((old) => ({ ...old, ...patch }));
  const playlist = meta?.playlists.find((item) => item.id === filters.playlist);
  const tracks = data?.tracks ?? [];
  return (
    <div className="space-y-4">
      {!online && <p role="status" className="flex items-center gap-2 text-sm text-fg-2"><CircleAlert aria-hidden className="size-4" />{S.s_mat_mang_chi_nghe_thu_duoc_bai_da_tai_cab0d6f8}</p>}
      <label className="relative block">
        <span className="sr-only">{S.s_tim_trong_kho_nhac_b9972ac9}</span>
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-2" />
        <input
          type="search" value={text} onChange={(event) => setText(event.target.value)} placeholder={S.s_tim_ten_bai_nguoi_sang_tac_fdee04f4}
          aria-label={S.s_tim_trong_kho_nhac_b9972ac9}
          className="h-[44px] w-full rounded-control bg-sunken pl-10 pr-11 text-sm outline-none placeholder:text-fg-2 focus:ring-2 focus:ring-focus [&::-webkit-search-cancel-button]:hidden"
        />
        {text && <IconButton size="sm" label={S.s_bo_loc_74de0064} icon={X} onClick={() => setText("")} className="absolute right-1.5 top-1/2 -translate-y-1/2" />}
      </label>
      <div role="group" aria-label={S.s_loc_kho_nhac_6c590fb5} className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none]">
        <ChipMenu label={S.s_danh_sach_phat_26862e10} value={filters.playlist} onChange={(value) => set({ playlist: value })}
          options={(meta?.playlists ?? []).map((item) => ({ value: item.id, label: item.name }))} />
        <ChipMenu label={S.s_phong_cach_d80ae8d9} value={filters.style} onChange={(value) => set({ style: value })}
          options={(meta?.styles ?? []).map((item) => ({ value: item.id, label: item.label }))} />
        <ChipMenu label={S.s_cam_xuc_05c1aee0} value={filters.emotion} onChange={(value) => set({ emotion: value })}
          options={(meta?.emotions ?? []).map((item) => ({ value: item.id, label: item.label }))} />
        <ChipMenu label={S.s_nhip_8a75919d} value={filters.tempo} onChange={(value) => set({ tempo: value as LibraryFilters["tempo"] })} options={TEMPO_OPTIONS} />
        <ChipMenu label={S.s_do_dai_5e055f59} value={filters.length} onChange={(value) => set({ length: value as LibraryFilters["length"] })} options={LENGTH_OPTIONS} />
        <button type="button" aria-pressed={filters.downloaded} onClick={() => set({ downloaded: !filters.downloaded })} className={chipClass(filters.downloaded)}>
          {S.s_da_tai_b7362bbf}
        </button>
      </div>
      <div className="flex min-h-10 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <p className="flex items-center gap-2 text-sm text-fg-2" aria-live="polite">
          {S.s_0_bai_1e392237(data?.count ?? 0)}
          {data && data.saved.count > 0 && <span>· {S.s_da_tai_0_bai_1_3cac202f(data.saved.count, formatSize(data.saved.bytes))}</span>}
          {isFetching && <Loader2 aria-hidden className="size-3.5 animate-spin" />}
        </p>
        <div className="flex items-center gap-2">
          {filtering(filters) && <Button size="sm" onClick={() => setFilters(NO_FILTERS)}>{S.s_bo_loc_74de0064}</Button>}
          {playlist && data && data.missingBytes > 0 && (
            <Button size="sm" variant="primary" icon={Download} loading={save.isPending} disabled={!online}
              onClick={() => save.mutate(tracks.filter((track) => !track.downloaded).map((track) => track.link))}>
              {S.s_tai_ca_danh_sach_0_63e52378(formatSize(data.missingBytes))}
            </Button>
          )}
        </div>
      </div>
      {isLoading ? (
        <ContentSkeleton count={6} />
      ) : (error && !data) || data?.error ? (
        <InlineError message={data?.error || S.s_chua_tai_duoc_kho_nhac_9577b7c7} onRetry={() => void refetch()} />
      ) : tracks.length ? (
        <div role="list" aria-label={S.s_kho_nhac_94affa81}>
          <Windowed
            memory="music-library"
            items={tracks}
            estimate={64}
            row={(track) => (
              <TrackRow key={track.link} track={track} preview={preview} downloads={downloads} online={online} styles={meta?.styles} onOpen={setOpen}
                onUse={use} as="div" />
            )}
          />
        </div>
      ) : (
        <EmptyState icon={Music2} title={S.s_khong_co_bai_nao_hop_5b5b11b5}
          action={filtering(filters) || text ? <Button onClick={() => { setFilters(NO_FILTERS); setText(""); }}>{S.s_bo_loc_74de0064}</Button> : undefined} />
      )}
      <TrackSheet link={open} onClose={() => setOpen(null)} preview={preview} onUse={use} onBan={ban} busy={busy} />
    </div>
  );
}

function chipClass(active: boolean): string {
  return cn(
    "press inline-flex h-10 shrink-0 items-center gap-1 whitespace-nowrap rounded-control px-3.5 text-sm font-medium transition-colors duration-motion-fast touch-reach",
    active ? "bg-accent text-accent-ink" : "bg-hover text-fg-2 hover:text-fg",
  );
}

/** Một chip lọc: chạm mở danh sách chọn ("Tất cả" + các mục); đang lọc thì chip mang tên mục đã chọn và đổi màu. */
function ChipMenu({ label, value, onChange, options }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: string }[];
}) {
  const chosen = options.find((option) => option.value === value);
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger asChild>
        <button type="button" aria-label={chosen ? `${label}: ${chosen.label}` : label} className={chipClass(Boolean(chosen))}>
          {chosen ? chosen.label : label}
          <ChevronDown aria-hidden className="ink-end [--icon-w:16px] size-4" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="start" sideOffset={4} collisionPadding={12} className="z-50 max-h-[min(420px,var(--radix-dropdown-menu-content-available-height))] min-w-48 overflow-y-auto overscroll-contain rounded-cover border border-line bg-panel p-1.5 shadow-float">
          <DropdownMenu.Label className="px-3 py-1.5 text-xs font-medium text-fg-2">{label}</DropdownMenu.Label>
          <DropdownMenu.RadioGroup value={value} onValueChange={onChange}>
            {[{ value: "", label: S.s_tat_ca_49c73a31 }, ...options].map((option) => (
              <DropdownMenu.RadioItem key={option.value || "all"} value={option.value}
                className="flex min-h-[44px] cursor-default items-center gap-3 rounded-control px-3 text-sm outline-none data-[highlighted]:bg-hover data-[state=checked]:text-accent-text">
                <SelectionMark selected={value === option.value} />{option.label}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

/** Một dòng bài: nút nghe thử · tên · người sáng tác · thời lượng · chip phong cách · trạng thái tải (nút tải / vòng % / đã tải). Chạm
 *  dòng mở chi tiết. Chế độ chọn: thêm nút "Dùng". Mất mạng: bài chưa tải mờ nút nghe thử. */
export function TrackRow({
  track,
  preview,
  downloads,
  online,
  onOpen,
  onUse,
  as: Item = "li",
  nested = false,
}: {
  track: LibraryTrack;
  preview: LibraryPreview;
  downloads: DownloadState | undefined;
  online: boolean;
  styles?: { id: string; label: string }[];
  onOpen: (link: string) => void;
  onUse?: (link: string) => void;
  as?: "li" | "div";
  /** Hàng nằm trong một `<li>` của danh sách khác (Nhạc trong sách) - khi ấy chính nó không phải mục danh sách. */
  nested?: boolean;
}) {
  const { save, unsave } = useSaveTracks();
  const load = loadOf(track, downloads);
  const previewing = preview.playing?.link === track.link;
  const playable = online || track.downloaded;
  const title = track.title || S.s_bai_nay_d9683a01;
  return (
    <Item role={Item === "div" && !nested ? "listitem" : undefined} className="flex min-h-16 items-center gap-2 border-b border-line py-1.5 last:border-b-0">
      <IconButton
        label={previewing ? S.s_dung_nghe_f20939be : S.s_nghe_thu_fa024065}
        icon={previewing ? Square : Play}
        aria-pressed={previewing}
        disabled={!playable}
        onClick={() => preview.toggle(track)}
        className={cn("music-row-preview", previewing && "text-accent-text")}
      />
      <button type="button" onClick={() => onOpen(track.link)} className="min-w-0 flex-1 rounded-control py-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-focus">
        <span className="line-clamp-2 text-sm font-medium">{title}</span>
        <DotJoin singleLine className="mt-0.5 text-xs text-fg-2" parts={[track.creator, typeof track.duration === "number" ? formatClock(track.duration) : null]} />
      </button>
      {onUse && <Button size="sm" variant="primary" onClick={() => onUse(track.link)}>{S.s_dung_7927ca4e}</Button>}
      {load.kind === "loading" ? (
        <button type="button" aria-label={S.s_huy_tai_1a9ff73d} title={S.s_huy_tai_1a9ff73d} onClick={() => unsave.mutate([track.link])}
          className="press relative grid size-9 shrink-0 place-items-center rounded-control text-accent-text hover:bg-hover touch-reach">
          <ProgressRing percent={load.percent} />
          <span className="sr-only">{S.s_dang_tai_0_e9a97892(load.percent ?? 0)}</span>
        </button>
      ) : load.kind === "done" ? (
        <span className="grid size-9 shrink-0 place-items-center text-success" title={S.s_da_tai_b7362bbf}>
          <Check aria-hidden className="size-4" />
          <span className="sr-only">{S.s_da_tai_b7362bbf}</span>
        </span>
      ) : (
        <IconButton
          label={load.kind === "failed" ? S.s_chua_tai_xong_b257419d : S.s_tai_ve_9b5bdb44}
          icon={load.kind === "failed" ? CircleAlert : Download}
          disabled={!online}
          onClick={() => save.mutate([track.link])}
          className={cn(load.kind === "failed" && "text-warning")}
        />
      )}
    </Item>
  );
}

function ProgressRing({ percent }: { percent: number | null }) {
  if (percent === null) return <Loader2 aria-hidden className="size-5 animate-spin" />;
  const circumference = 2 * Math.PI * 16;
  return (
    <svg aria-hidden viewBox="0 0 36 36" className="size-9">
      <circle cx="18" cy="18" r="16" fill="none" stroke="currentColor" strokeOpacity={0.2} strokeWidth={2.5} />
      <circle cx="18" cy="18" r="16" transform="rotate(-90 18 18)" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={circumference * (1 - percent / 100)} />
      <text data-motion-live x="18" y="18" textAnchor="middle" dominantBaseline="central" className="fill-current text-xs">{percent}%</text>
    </svg>
  );
}
