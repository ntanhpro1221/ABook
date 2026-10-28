import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
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

// Cuốn mở từ file dự án `.abookproj` (docs/EDITING.md, phase P3): xưởng đi theo cuốn (hay đang chờ), kèm vài bản chụp CHỈ ĐỌC của
// các màn Studio để điện thoại / máy chưa cài Studio cho người ta xem mà không mở sổ dự án.

const MENU_ITEM =
  "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover";

/** Chữ nói rõ cái giá của “Dựng xưởng” - người nghe nhận ra cái họ mất, không phải cách nó chạy. */
export const WORKSHOP_COST =
  "Studio sẽ tạo một dự án mới từ chữ và giọng của cuốn này, mang theo tên bạn đặt và những việc bạn ghi cho Studio. " +
  "Không còn dự án gốc: audio sẽ làm lại hết. Cuốn đang nghe giữ nguyên.";

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
        action: { label: "Mở dự án", onClick: () => navigate(`/studio/${made.id}`) },
      });
    } catch (error) {
      toast.error("Chưa dựng được xưởng", { description: (error as Error).message });
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
    <DropdownMenu.Item disabled className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}>
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
    <DropdownMenu.Item onSelect={() => navigate("/studio")} className={cn(MENU_ITEM, "h-auto items-start py-1.5")}>
      <Wrench className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">{title}</span>
        <span className="block text-xs text-fg-3">
          {studio.repair ? "Studio cần sửa - " : studio.update ? "Cần cập nhật Studio - " : "Cần cài Studio (card NVIDIA) - "}
          <span className="font-medium text-accent-text underline">{studio.action}</span>
        </span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Chữ nói rõ “Tạo sách nói” mang gì sang Studio. */
export const TEXT_BOOK_COST =
  "Tạo dự án Studio từ chữ cuốn này. Chưa chạy gì; cuốn đang đọc giữ nguyên.";

/** Mục menu của sách chỉ có chữ (nhập từ EPUB / DOCX / PDF / TXT): “Tạo sách nói” (máy có Studio) hay mở dự án đã làm. */
export function TextBookItems({ book }: { book: ListenBook }) {
  const navigate = useNavigate();
  const { build, building } = useBuildProject(book, (made) => `Đã tạo dự án Studio · ${made.chapters} chương`);
  if (book.stage !== "text") return null;
  const toolchain = Boolean(book.capabilities?.toolchain);
  if (book.studioProject) {
    return (
      <DropdownMenu.Item onSelect={() => navigate(`/studio/${book.studioProject}`)} className={MENU_ITEM}>
        <Hammer className="size-4" /> Mở dự án Studio
      </DropdownMenu.Item>
    );
  }
  if (!toolchain) return <NeedStudioItem title="Tạo sách nói" phoneNote="Chỉ làm được ở Studio trên máy tính. Ở đây bạn vẫn nghe cuốn này bằng Nghe ngay." />;
  return (
    <DropdownMenu.Item
      disabled={building}
      onSelect={() => void build()}
      className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}
    >
      <Hammer className="mt-line-icon size-4 shrink-0" />
      <span className="min-w-0">
        <span className="block">Tạo sách nói</span>
        <span className="block text-xs text-fg-3">{TEXT_BOOK_COST}</span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Mục menu của cuốn từ file dự án: mở bản chụp xưởng, “Dựng xưởng” (cuốn chờ xưởng, máy có Studio) hay mở xưởng đã dựng. */
export function ProjectFileItems({ book, onViews }: { book: ListenBook; onViews: () => void }) {
  const info = book.projectFile;
  const navigate = useNavigate();
  const { build, building } = useBuildProject(book, (made) => `Đã dựng xưởng · ${made.chapters} chương, ${made.voices} giọng`);
  if (!info) return null;
  const pending = info.workshop === "pending";
  const toolchain = Boolean(book.capabilities?.toolchain);
  return (
    <>
      {info.views.length > 0 && (
        <DropdownMenu.Item onSelect={onViews} className={MENU_ITEM}>
          <ClipboardList className="size-4" /> Việc của xưởng
        </DropdownMenu.Item>
      )}
      {pending && info.built && (
        <DropdownMenu.Item onSelect={() => navigate(`/studio/${info.built}`)} className={MENU_ITEM}>
          <Hammer className="size-4" /> Mở xưởng đã dựng
        </DropdownMenu.Item>
      )}
      {pending && !info.built && !toolchain && <NeedStudioItem title="Dựng xưởng" phoneNote="Cần cài Studio - file này chỉ mang phần nghe, chưa có xưởng" />}
      {pending && !info.built && toolchain && (
        <DropdownMenu.Item
          disabled={building}
          onSelect={() => void build()}
          className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}
        >
          <Hammer className="mt-line-icon size-4 shrink-0" />
          <span className="min-w-0">
            <span className="block">Dựng xưởng</span>
            <span className="block text-xs text-fg-3">{WORKSHOP_COST}</span>
          </span>
        </DropdownMenu.Item>
      )}
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
    { value: "work", label: "Việc cần duyệt" },
    { value: "casting", label: "Kịch bản" },
    { value: "names", label: "Cách đọc tên" },
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
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Đóng
        </Button>
      </DialogActions>}
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-[560px]"
      title="Việc của xưởng"
      description="Ảnh chụp lúc người làm sách đóng gói file - chỉ để xem. Muốn sửa thì mở file bằng Studio."
    >
      {available.length > 1 && <ChoiceRow<Tab> value={tab} onChange={setTab} label="Màn" options={available} />}
      {/* Khung chờ / lỗi / đổi màn: mờ qua (fadeThrough) theo khoá màn + pha tải, không đổi cứng trong hộp đang mở. */}
      <MotionRegion elementRef={scrollFade.ref} style={scrollFade.style} fadeThrough motionKey={[tab, isLoading, Boolean(error && !data)]} className="mt-3 max-h-[50vh] overflow-y-auto text-sm">
        {isLoading ? <ContentSkeleton label="Đang tải việc xưởng" /> : error && !data ? <InlineError message="Bạn hãy thử tải lại việc của xưởng." onRetry={() => void refetch()} /> : null}
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
    decided > 0 ? `${decided} việc đã quyết, chờ áp dụng` : "",
    later > 0 ? `${later} việc chỉ có tác dụng khi làm lại phân tích` : "",
  ].filter(Boolean);
  return (
    <>
      {open.length ? (
        <ul className="divide-y divide-line">
          {open.map((item) => (
            <li key={item.key} className="py-2">
              <p>{item.title}</p>
              {item.problem && <p className="text-xs text-fg-3">{item.problem}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <Empty>{rest.length ? "Không còn việc nào cần quyết." : "Máy không còn chỗ nào nghi ngờ."}</Empty>
      )}
      {rest.length > 0 && <p className="mt-3 text-xs text-fg-3">Ngoài ra: {rest.join(" · ")}.</p>}
    </>
  );
}

function CastingList({ data }: { data?: CastingSnapshot }) {
  if (!data) return null;
  if (!data.chapters?.length) return <Empty>Chưa có chương nào được phân vai.</Empty>;
  return (
    <ul className="divide-y divide-line">
      {data.chapters.map((chapter) => (
        <li key={chapter.chapterId} className="flex items-baseline justify-between gap-3 py-2">
          <span className="min-w-0 [overflow-wrap:anywhere] whitespace-normal">{chapter.title || `Chương ${chapter.chapterId}`}</span>
          <span className="shrink-0 text-xs text-fg-3">
            {chapter.speech} câu thoại{chapter.hints ? ` · ${chapter.hints} chỗ máy nghi` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

function NamesList({ data }: { data?: NamesSnapshot }) {
  if (!data) return null;
  if (!data.items?.length) return <Empty>Chưa có tên riêng nào cần ghi cách đọc.</Empty>;
  return (
    <ul className="divide-y divide-line">
      {data.items.map((item) => (
        <li key={item.surface} className="flex items-baseline justify-between gap-3 py-2">
          <span className="min-w-0 [overflow-wrap:anywhere] whitespace-normal">
            {item.surface} → {item.spoken}
          </span>
          <span className="shrink-0 text-xs text-fg-3">
            {item.byListener ? "bạn đã chọn · " : ""}
            {item.lines} câu
          </span>
        </li>
      ))}
    </ul>
  );
}
