import { useQuery } from "@tanstack/react-query";
import { AudioLines, Pause, Play } from "lucide-react";
import { useState } from "react";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button, EmptyState, Segmented } from "@/shared/ui";
import { api, urls } from "./api";

// "Việc cần anh" (docs/STUDIO_REVIEW.md, webui/work_items.py): chỗ máy nghi ngờ, xếp theo lợi trên mỗi lần bấm. Máy đã tự
// quyết và dây chuyền KHÔNG chờ ai - đây là nơi người sửa ít nhất mà được nhiều nhất. Bước 1 chỉ đọc; sửa trực tiếp là bước 2.

type WorkKind = "gender" | "vocative" | "alias" | "shared-voice" | "pronunciation" | "unnamed" | "audio";

interface WorkExample {
  segmentId: number;
  chapterId: number;
  chapterTitle: string;
  seq: number;
  text: string;
  speaker: string;
}

interface WorkItem {
  kind: WorkKind;
  key: string;
  title: string;
  problem: string;
  affected: number;
  doubt: number;
  score: number;
  options: string[];
  current: string;
  examples: WorkExample[];
}

interface WorkView {
  items: WorkItem[];
  counts: Partial<Record<WorkKind, number>>;
}

const KIND_LABEL: Record<WorkKind, string> = {
  pronunciation: "Cách đọc tên",
  gender: "Nam hay nữ",
  vocative: "Người gọi hay người nói",
  alias: "Một người hai tên",
  "shared-voice": "Chung giọng",
  unnamed: "Vai phụ không tên",
  audio: "Bản thu lỗi",
};

const PAGE = 40;

export function useWorkCount(bookId: string) {
  const { data } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
    enabled: Boolean(bookId),
    staleTime: 60_000,
  });
  return data?.items.length ?? 0;
}

function Example({ bookId, example }: { bookId: string; example: WorkExample }) {
  const clip = useClip();
  const id = `work-${example.segmentId}`;
  const playing = clip.current === id;
  return (
    <li className="flex items-start gap-2 text-sm">
      <button
        type="button"
        onClick={() => clip.toggle(id, urls.sample(bookId, example.segmentId))}
        aria-label={playing ? "Dừng" : `Nghe câu: ${example.text}`}
        className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-hover text-fg-2 hover:text-fg"
      >
        {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
      </button>
      <div className="min-w-0">
        <div className="text-xs text-fg-3">
          {example.chapterTitle} · câu {example.seq}
          {example.speaker && ` · máy gán: ${example.speaker}`}
        </div>
        <p className="text-fg">{example.text}</p>
      </div>
    </li>
  );
}

function Card({ bookId, item, onOpenReview }: { bookId: string; item: WorkItem; onOpenReview: () => void }) {
  return (
    <li className="rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="rounded-full bg-hover px-2 py-0.5 text-[11px] font-medium text-fg-2">{KIND_LABEL[item.kind]}</span>
        <h3 className="text-[15px] font-semibold">{item.title}</h3>
      </div>
      <p className="mt-1.5 text-sm text-fg-2">{item.problem}</p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-2">
        <span>
          Ảnh hưởng <span className="tabular font-semibold text-fg">{formatNumber(item.affected)}</span> câu
        </span>
        <span>
          Máy đang dùng: <span className="font-medium text-fg">{item.current}</span>
        </span>
      </div>
      {item.kind === "audio" ? (
        <Button size="sm" variant="secondary" icon={AudioLines} className="mt-3" onClick={onOpenReview}>
          Nghe ở tab Cần nghe lại
        </Button>
      ) : (
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Lựa chọn">
          {item.options.map((option) => (
            <span key={option} className="rounded-lg border border-line px-2.5 py-1 text-xs text-fg-2">
              {option}
            </span>
          ))}
        </div>
      )}
      {item.examples.length > 0 && (
        <ul className="mt-3 space-y-2 border-t border-line pt-3">
          {item.examples.map((example) => (
            <Example key={example.segmentId} bookId={bookId} example={example} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function WorkInbox({ bookId, onOpenReview }: { bookId: string; onOpenReview: () => void }) {
  const [kind, setKind] = useState<WorkKind | "all">("all");
  const [shown, setShown] = useState(PAGE);
  const { data, isLoading } = useQuery({
    queryKey: ["work", bookId],
    queryFn: () => api<WorkView>(`/api/books/${bookId}/work`),
  });
  if (isLoading || !data) return <div className="mt-6 text-sm text-fg-2">Đang tìm những chỗ máy chưa chắc…</div>;
  if (!data.items.length) {
    return (
      <EmptyState icon={AudioLines} title="Không có việc gì cần anh" className="py-10">
        Máy chắc chắn về mọi thứ đã làm tới giờ.
      </EmptyState>
    );
  }
  const kinds = (Object.keys(KIND_LABEL) as WorkKind[]).filter((value) => data.counts[value]);
  const items = data.items.filter((item) => kind === "all" || item.kind === kind);
  return (
    <div className="mt-5">
      <p className="max-w-3xl text-sm text-fg-2">
        Máy đã tự quyết và đang chạy tiếp - không có gì phải chờ anh. Đây là những chỗ nó không chắc, xếp theo lợi: việc ở
        trên sửa một lần được nhiều câu nhất. Bước này để xem; sửa trực tiếp từng việc sẽ có ở bước kế.
      </p>
      <div className="mt-4 overflow-x-auto">
        <Segmented<WorkKind | "all">
          label="Loại việc"
          value={kind}
          onChange={(value) => {
            setKind(value);
            setShown(PAGE);
          }}
          options={[
            { value: "all", label: `Tất cả · ${data.items.length}` },
            ...kinds.map((value) => ({ value, label: `${KIND_LABEL[value]} · ${data.counts[value]}` })),
          ]}
        />
      </div>
      <ol className={cn("mt-4 space-y-3")}>
        {items.slice(0, shown).map((item) => (
          <Card key={item.key} bookId={bookId} item={item} onOpenReview={onOpenReview} />
        ))}
      </ol>
      {items.length > shown && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={() => setShown(shown + PAGE)}>
          Xem thêm {Math.min(PAGE, items.length - shown)} việc
        </Button>
      )}
    </div>
  );
}
