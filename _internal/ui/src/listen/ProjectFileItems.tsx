import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@/shared/DropdownMenu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Hammer, Wrench } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { DialogActions, Button, Dialog, ChoiceRow, ContentSkeleton, InlineError } from "@/shared/ui";
import { api } from "@/studio/api";
import { useStudioMissing } from "@/studio/data";
import { isOpenWork } from "@/studio/precast";
import type { ListenBook } from "./model";
import { useSource } from "./source";
import { useFadeScroller } from "@/shared/scrollFade";

import { Reveal } from "../shared/MotionPresence";
// Cuốn mở từ file dự án `.abookproj` (docs/EDITING.md, phase P3): xưởng đi theo cuốn (hay đang chờ), kèm vài bản chụp CHỈ ĐỌC của
// các màn Studio để điện thoại / máy chưa cài Studio cho người ta xem mà không mở sổ dự án.

const MENU_ITEM =
  "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover";

/** Chữ nói rõ cái giá của “Dựng xưởng” - người nghe nhận ra cái họ mất, không phải cách nó chạy. */
export const WORKSHOP_COST =
  S.s_studio_se_tao_mot_du_an_moi_tu_chu_va_gion_500db53d +
  S.s_khong_con_du_an_goc_audio_se_lam_lai_het_c_a2a1a61a;

/** “Dựng xưởng” / “Tạo sách nói”: một dự án Studio mới từ cuốn đang nghe / đọc (`POST /api/books/<mã>/workshop`, workshop.py).
 *  `done` nói điều đã mang sang, theo loại cuốn. */
function useBuildProject(book: ListenBook, done: (made: { chapters: number; voices: number }) => string) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [building, setBuilding] = useState(false);
  const build = async () => {
    setBuilding(true);
    try {
      const made = await api<{ id: string; chapters: number; voices: number }>(`/api/books/${book.id}/workshop`, { method: "POST", body: {} });
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["listen"] });
      toast.success(done(made), {
        action: { label: S.s_mo_du_an_f990c9d8, onClick: () => navigate(`/studio/${made.id}`) },
      });
    } catch (error) {
      toast.error(S.s_chua_dung_duoc_xuong_c69867f7, { description: (error as Error).message });
    } finally {
      setBuilding(false);
    }
  };
  return { build, building };
}

/** Mục mờ của việc cần Studio khi máy chưa có. Trên máy tính, Studio cài được ngay ở đây: dòng phụ nói cần gì và bấm là tới thẻ “Cài Studio”
 *  (đầu màn Dự án). Điện thoại không có Studio để cài - giữ lời riêng của điện thoại. */
function NeedStudioItem({ title, phoneNote }: { title: string; phoneNote: string }) {
  const source = useSource();
  if (source.kind === "android") return <DisabledNeedItem title={title} note={phoneNote} />;
  return <DesktopNeedStudioItem title={title} note={phoneNote} />;
}

function DisabledNeedItem({ title, note }: { title: string; note: string }) {
  return (
    <DropdownMenu.Item disabled className={cn(MENU_ITEM, "h-auto items-start py-2 data-[disabled]:opacity-60")}>
      <Wrench className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{title}</span>
        <span className="block text-xs text-fg-3">{note}</span>
      </span>
    </DropdownMenu.Item>
  );
}

function DesktopNeedStudioItem({ title, note }: { title: string; note: string }) {
  const navigate = useNavigate();
  const studio = useStudioMissing();
  if (!studio.missing) return <DisabledNeedItem title={title} note={note} />;
  return (
    <DropdownMenu.Item onSelect={() => navigate("/studio")} className={cn(MENU_ITEM, "h-auto items-start py-2")}>
      <Wrench className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{title}</span>
        <span className="block text-xs text-fg-3">
          {studio.repair ? S.s_studio_can_sua_df3737b2 : studio.update ? S.s_can_cap_nhat_studio_55da602b : S.s_can_cai_studio_card_nvidia_04f7c5f8}
          <span className="font-medium text-accent-text underline">{studio.action}</span>
        </span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Chữ nói rõ “Tạo sách nói” mang gì sang Studio. */
export const TEXT_BOOK_COST =
  S.s_tao_du_an_studio_tu_chu_cuon_nay_chua_chay_667f3623;

/** Mục menu của sách chỉ có chữ (nhập từ EPUB / DOCX / PDF / TXT): “Tạo sách nói” (máy có Studio) hay mở dự án đã làm. */
export function TextBookItems({ book }: { book: ListenBook }) {
  const navigate = useNavigate();
  const { build, building } = useBuildProject(book, (made) => S.s_da_tao_du_an_studio_0_chuong_247e4db3(made.chapters));
  if (book.stage !== "text") return null;
  const toolchain = Boolean(book.capabilities?.toolchain);
  if (book.studioProject) {
    return (
      <DropdownMenu.Item onSelect={() => navigate(`/studio/${book.studioProject}`)} className={MENU_ITEM}>
        <Hammer className="size-4" />{S.s_mo_du_an_studio_9ead1ad4}</DropdownMenu.Item>
    );
  }
  if (!toolchain) return <NeedStudioItem title={S.s_tao_sach_noi_ab873c7a} phoneNote={S.s_chi_lam_duoc_o_studio_tren_may_tinh_o_day_a481062a} />;
  return (
    <DropdownMenu.Item
      disabled={building}
      onSelect={() => void build()}
      className={cn(MENU_ITEM, "h-auto items-start py-2 data-[disabled]:opacity-60")}
    >
      <Hammer className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{S.s_tao_sach_noi_ab873c7a}</span>
        <span className="block text-xs text-fg-3">{TEXT_BOOK_COST}</span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Mục menu của cuốn từ file dự án: mở bản chụp xưởng, “Dựng xưởng” (cuốn chờ xưởng, máy có Studio) hay mở xưởng đã dựng. */
export function ProjectFileItems({ book, onViews }: { book: ListenBook; onViews: () => void }) {
  const info = book.projectFile;
  const navigate = useNavigate();
  const { build, building } = useBuildProject(book, (made) => S.s_da_dung_xuong_0_chuong_1_giong_9135690f(made.chapters, made.voices));
  if (!info) return null;
  const pending = info.workshop === "pending";
  const toolchain = Boolean(book.capabilities?.toolchain);
  return (
    <>
      <Reveal when={info.views.length > 0}><DropdownMenu.Item onSelect={onViews} className={MENU_ITEM}>
          <ClipboardList className="size-4" />{S.s_viec_cua_xuong_4471031f}</DropdownMenu.Item></Reveal>
      <Reveal when={pending && info.built}><DropdownMenu.Item onSelect={() => navigate(`/studio/${info.built}`)} className={MENU_ITEM}>
          <Hammer className="size-4" />{S.s_mo_xuong_da_dung_4a9a2211}</DropdownMenu.Item></Reveal>
      {pending && !info.built && !toolchain && <NeedStudioItem title={S.s_dung_xuong_186ba1e1} phoneNote={S.s_can_cai_studio_file_nay_chi_mang_phan_nghe_a924b6b8} />}
      <Reveal when={pending && !info.built && toolchain}><DropdownMenu.Item
          disabled={building}
          onSelect={() => void build()}
          className={cn(MENU_ITEM, "h-auto items-start py-2 data-[disabled]:opacity-60")}
        >
          <Hammer className="mt-line-icon size-4 shrink-0" />
          <span className="min-w-0">
            <span className="block">{S.s_dung_xuong_186ba1e1}</span>
            <span className="block text-xs text-fg-3">{WORKSHOP_COST}</span>
          </span>
        </DropdownMenu.Item></Reveal>
    </>
  );
}

type Tab = "work" | "casting" | "names";

interface WorkItem {
  key: string;
  title: string;
  problem?: string;
  affected?: number;
  /** Đã quyết (chờ áp dụng) - như thẻ của tab Việc cần duyệt. */
  requested?: string | null;
  /** Chỉ có tác dụng khi làm lại phân tích từ đầu. */
  redoOnly?: boolean;
}

interface WorkSnapshot {
  items: WorkItem[];
}

interface CastingSnapshot {
  chapters: { chapterId: number; title: string; lines: number; speech: number; hints: number; decided: number }[];
}

interface NamesSnapshot {
  items: { surface: string; spoken: string; lines: number; byListener: boolean }[];
}

/** Bản chụp chỉ đọc của xưởng trong file dự án: việc máy nghi ngờ, mục lục kịch bản, cách đọc tên. Không sửa được ở đây. */
export function ProjectViewsDialog({ book, open, onOpenChange }: { book: ListenBook; open: boolean; onOpenChange: (open: boolean) => void }) {
  const scrollFade = useFadeScroller<HTMLElement>();
  const views = book.projectFile?.views ?? [];
  const tabs: { value: Tab; label: string }[] = [
    { value: "work", label: S.s_viec_can_duyet_5c0c3ce1 },
    { value: "casting", label: S.s_kich_ban_602e5f27 },
    { value: "names", label: S.s_cach_doc_ten_1c46e75d },
  ];
  const available = tabs.filter((tab) => views.includes(tab.value));
  const [chosen, setTab] = useState<Tab>("work");
  const tab = available.some((item) => item.value === chosen) ? chosen : (available[0]?.value ?? "work");
  const path = { work: "work", casting: "casting", names: "pronunciations" }[tab];
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["project-view", book.id, tab],
    queryFn: () => api<WorkSnapshot | CastingSnapshot | NamesSnapshot>(`/api/books/${book.id}/${path}`),
    enabled: open && available.length > 0,
  });
  return (
    <Dialog footer={<DialogActions>
        <Button variant="ghost" onClick={() => onOpenChange(false)}>{S.s_dong_5d54c2a1}</Button>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-[560px]"
      title={S.s_viec_cua_xuong_bfea3878}
      description={S.s_anh_chup_luc_nguoi_lam_sach_dong_goi_file_bd6bbbbf}
    >
      {available.length > 1 && <ChoiceRow<Tab> value={tab} onChange={setTab} label={S.s_man_47a0e3c8} options={available} />}
      {/* Khung chờ / lỗi / đổi màn: mờ qua (fadeThrough) theo khoá màn + pha tải, không đổi cứng trong hộp đang mở. */}
      <MotionRegion elementRef={scrollFade.ref} style={scrollFade.style} fadeThrough motionKey={[tab, isLoading, Boolean(error && !data)]} className="mt-3 max-h-[50vh] overflow-y-auto text-sm">
        {isLoading ? <ContentSkeleton label={S.s_dang_tai_viec_xuong_571590f2} /> : error && !data ? <InlineError message={S.s_ban_hay_thu_tai_lai_viec_cua_xuong_3c08f0cd} onRetry={() => void refetch()} /> : null}
        {tab === "work" && <WorkList data={data as WorkSnapshot | undefined} />}
        {tab === "casting" && <CastingList data={data as CastingSnapshot | undefined} />}
        {tab === "names" && <NamesList data={data as NamesSnapshot | undefined} />}
      </MotionRegion>

    </Dialog>
  );
}

function Empty({ children }: { children: string }) {
  return <p className="text-fg-3">{children}</p>;
}

/** Như tab Việc cần duyệt (WorkInbox): chỉ liệt kê việc còn chờ quyết mà quyết thì có tác dụng; việc đã quyết và việc chỉ áp khi
 *  làm lại phân tích chỉ được đếm ở cuối. */
function WorkList({ data }: { data?: WorkSnapshot }) {
  if (!data) return null;
  const items = data.items ?? [];
  const open = items.filter(isOpenWork);
  const decided = items.filter((item) => item.requested).length;
  const later = items.filter((item) => !item.requested && item.redoOnly).length;
  const rest = [
    decided > 0 ? S.s_0_viec_da_quyet_cho_ap_dung_c1a9df50(decided) : "",
    later > 0 ? S.s_0_viec_chi_co_tac_dung_khi_lam_lai_phan_ti_f4942454(later) : "",
  ].filter(Boolean);
  return (
    <>
      {open.length ? (
        <ul className="divide-y divide-line">
          {open.map((item) => (
            <li key={item.key} className="py-2">
              <p>{item.title}</p>
              <Reveal when={item.problem}><p className="text-xs text-fg-3">{item.problem}</p></Reveal>
            </li>
          ))}
        </ul>
      ) : (
        <Empty>{rest.length ? S.s_khong_con_viec_nao_can_quyet_4cccb08f : S.s_may_khong_con_cho_nao_nghi_ngo_5bcb5676}</Empty>
      )}
      <Reveal when={rest.length > 0}><p className="mt-3 text-xs text-fg-3">{S.s_ngoai_ra_41b5d544}{rest.join(" · ")}.</p></Reveal>
    </>
  );
}

function CastingList({ data }: { data?: CastingSnapshot }) {
  if (!data) return null;
  if (!data.chapters?.length) return <Empty>{S.s_chua_co_chuong_nao_duoc_phan_vai_6a126e57}</Empty>;
  return (
    <ul className="divide-y divide-line">
      {data.chapters.map((chapter) => (
        <li key={chapter.chapterId} className="flex items-baseline justify-between gap-3 py-2">
          <span className="min-w-0 break-words">{chapter.title || S.s_chuong_0_268b0521(chapter.chapterId)}</span>
          <span className="shrink-0 text-xs text-fg-3">
            {chapter.speech}{S.s_cau_thoai_0bf070fe}{chapter.hints ? S.s_0_cho_may_nghi_886300ca(chapter.hints) : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

function NamesList({ data }: { data?: NamesSnapshot }) {
  if (!data) return null;
  if (!data.items?.length) return <Empty>{S.s_chua_co_ten_rieng_nao_can_ghi_cach_doc_635443e9}</Empty>;
  return (
    <ul className="divide-y divide-line">
      {data.items.map((item) => (
        <li key={item.surface} className="flex items-baseline justify-between gap-3 py-2">
          <span className="min-w-0 truncate">
            {item.surface} → {item.spoken}
          </span>
          <span className="shrink-0 text-xs text-fg-3">
            {item.byListener ? S.s_ban_da_chon_1ab9b9d8 : ""}
            {item.lines}{S.s_cau_b07e1008}</span>
        </li>
      ))}
    </ul>
  );
}
