import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Hammer, Wrench } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { Button, Dialog, Segmented } from "@/shared/ui";
import { api } from "@/studio/api";
import type { ListenBook } from "./model";

// Cuốn mở từ file dự án `.abookproj` (docs/EDITING.md, phase P3): xưởng đi theo cuốn (hay đang chờ), kèm vài bản chụp CHỈ ĐỌC của
// các màn Studio để điện thoại / máy chưa cài Studio cho người ta xem mà không mở sổ dự án.

const MENU_ITEM =
  "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[disabled]:opacity-40 data-[highlighted]:bg-hover";

/** Chữ nói rõ cái giá của “Dựng xưởng” - người nghe nhận ra cái họ mất, không phải cách nó chạy. */
export const WORKSHOP_COST =
  "Studio sẽ tạo một dự án mới từ chữ và giọng của cuốn này, mang theo tên bạn đặt và những việc bạn ghi cho Studio. " +
  "Không còn nguồn chương gốc, lịch sử phân tích, từng câu đã thu - toàn bộ audio sẽ được làm lại khi chạy. Cuốn đang nghe vẫn giữ nguyên.";

/** “Dựng xưởng” / “Làm sách nói từ cuốn này”: một dự án Studio mới từ cuốn đang nghe / đọc (`POST /api/books/<mã>/workshop`, workshop.py).
 *  `done` nói điều đã mang sang, theo loại cuốn. */
function useBuildProject(book: ListenBook, done: (made: { chapters: number; voices: number }) => { title: string; description: string }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [building, setBuilding] = useState(false);
  const build = async () => {
    setBuilding(true);
    try {
      const made = await api<{ id: string; chapters: number; voices: number }>(`/api/books/${book.id}/workshop`, { method: "POST", body: {} });
      void client.invalidateQueries({ queryKey: ["library"] });
      void client.invalidateQueries({ queryKey: ["listen"] });
      const said = done(made);
      toast.success(said.title, {
        description: said.description,
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

/** Chữ nói rõ “Làm sách nói từ cuốn này” mang gì sang Studio. */
export const TEXT_BOOK_COST =
  "Studio sẽ tạo một dự án mới từ chữ các chương của cuốn này, mang theo tên sách và bìa bạn đặt. Chưa chạy gì - chọn giọng kể rồi bắt đầu làm audio ở Studio. Cuốn đang đọc vẫn giữ nguyên.";

/** Mục menu của sách chỉ có chữ (nhập từ EPUB / DOCX / PDF / TXT): “Làm sách nói từ cuốn này” (máy có Studio) hay mở dự án đã làm. */
export function TextBookItems({ book }: { book: ListenBook }) {
  const navigate = useNavigate();
  const { build, building } = useBuildProject(book, (made) => ({
    title: "Đã tạo dự án Studio",
    description: `${made.chapters} chương. Chưa chạy gì - mở dự án để chọn giọng và bắt đầu.`,
  }));
  if (book.stage !== "text") return null;
  const toolchain = Boolean(book.capabilities?.toolchain);
  if (book.studioProject) {
    return (
      <DropdownMenu.Item onSelect={() => navigate(`/studio/${book.studioProject}`)} className={MENU_ITEM}>
        <Hammer className="size-4" /> Mở dự án đã làm từ cuốn này
      </DropdownMenu.Item>
    );
  }
  return (
    <DropdownMenu.Item
      disabled={!toolchain || building}
      onSelect={() => void build()}
      className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}
    >
      {toolchain ? <Hammer className="mt-0.5 size-4 shrink-0" /> : <Wrench className="mt-0.5 size-4 shrink-0" />}
      <span className="min-w-0">
        <span className="block">Làm sách nói từ cuốn này</span>
        <span className="block text-xs text-fg-3">{toolchain ? TEXT_BOOK_COST : "Cần cài Studio trên máy tính - ở đây cuốn này chỉ để đọc"}</span>
      </span>
    </DropdownMenu.Item>
  );
}

/** Mục menu của cuốn từ file dự án: mở bản chụp xưởng, “Dựng xưởng” (cuốn chờ xưởng, máy có Studio) hay mở xưởng đã dựng. */
export function ProjectFileItems({ book, onViews }: { book: ListenBook; onViews: () => void }) {
  const info = book.projectFile;
  const navigate = useNavigate();
  const { build, building } = useBuildProject(book, (made) => ({
    title: "Đã dựng xưởng",
    description: `${made.chapters} chương, ${made.voices} giọng nhân vật đã gieo. Chưa chạy gì - mở dự án để bắt đầu.`,
  }));
  if (!info) return null;
  const pending = info.workshop === "pending";
  const toolchain = Boolean(book.capabilities?.toolchain);
  return (
    <>
      {info.views.length > 0 && (
        <DropdownMenu.Item onSelect={onViews} className={MENU_ITEM}>
          <ClipboardList className="size-4" /> Việc của xưởng (chỉ đọc)
        </DropdownMenu.Item>
      )}
      {pending && info.built && (
        <DropdownMenu.Item onSelect={() => navigate(`/studio/${info.built}`)} className={MENU_ITEM}>
          <Hammer className="size-4" /> Mở xưởng đã dựng
        </DropdownMenu.Item>
      )}
      {pending && !info.built && (
        <DropdownMenu.Item
          disabled={!toolchain || building}
          onSelect={() => void build()}
          className={cn(MENU_ITEM, "h-auto items-start py-1.5 data-[disabled]:opacity-60")}
        >
          {toolchain ? <Hammer className="mt-0.5 size-4 shrink-0" /> : <Wrench className="mt-0.5 size-4 shrink-0" />}
          <span className="min-w-0">
            <span className="block">Dựng xưởng</span>
            <span className="block text-xs text-fg-3">{toolchain ? WORKSHOP_COST : "Cần cài Studio - file này chỉ mang phần nghe, chưa có xưởng"}</span>
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
  const { data, isLoading } = useQuery({
    queryKey: ["project-view", book.id, tab],
    queryFn: () => api<WorkSnapshot | CastingSnapshot | NamesSnapshot>(`/api/books/${book.id}/${path}`),
    enabled: open && available.length > 0,
  });
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      width="max-w-xl"
      title="Việc của xưởng"
      description="Ảnh chụp lúc người làm sách đóng gói file - chỉ để xem. Muốn sửa thì mở file bằng Studio."
    >
      {available.length > 1 && <Segmented<Tab> value={tab} onChange={setTab} label="Màn" options={available} />}
      <div className="mt-3 max-h-[50vh] overflow-y-auto text-sm">
        {isLoading && <p className="text-fg-3">Đang đọc…</p>}
        {tab === "work" && <WorkList data={data as WorkSnapshot | undefined} />}
        {tab === "casting" && <CastingList data={data as CastingSnapshot | undefined} />}
        {tab === "names" && <NamesList data={data as NamesSnapshot | undefined} />}
      </div>
      <div className="mt-4 flex justify-end">
        <Button variant="ghost" onClick={() => onOpenChange(false)}>
          Đóng
        </Button>
      </div>
    </Dialog>
  );
}

function Empty({ children }: { children: string }) {
  return <p className="text-fg-3">{children}</p>;
}

function WorkList({ data }: { data?: WorkSnapshot }) {
  if (!data) return null;
  if (!data.items?.length) return <Empty>Máy không còn chỗ nào nghi ngờ.</Empty>;
  return (
    <ul className="divide-y divide-line">
      {data.items.map((item) => (
        <li key={item.key} className="py-2">
          <p>{item.title}</p>
          {item.problem && <p className="text-xs text-fg-3">{item.problem}</p>}
        </li>
      ))}
    </ul>
  );
}

function CastingList({ data }: { data?: CastingSnapshot }) {
  if (!data) return null;
  if (!data.chapters?.length) return <Empty>Chưa có chương nào được phân vai.</Empty>;
  return (
    <ul className="divide-y divide-line">
      {data.chapters.map((chapter) => (
        <li key={chapter.chapterId} className="flex items-baseline justify-between gap-3 py-2">
          <span className="min-w-0 truncate">{chapter.title || `Chương ${chapter.chapterId}`}</span>
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
          <span className="min-w-0 truncate">
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
