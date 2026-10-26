import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence } from "@/shared/MotionPresence";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { shownReading } from "@/shared/format";
import { Button, IconButton } from "@/shared/ui";
import { api } from "./api";
import { refreshAfterDecision } from "./decisions";

// Cách đọc dùng chung cho mọi sách (webui/shared_readings.py): sửa một tên một lần, sách MỚI có tên ấy tự dùng (lúc tạo),
// sách có sẵn thì bấm "Dùng cách đọc chung". Mọi mục đi đúng đường của một lần sửa tay - dây chuyền áp ở ranh giới chương.

export interface SharedReading {
  surface: string;
  spokenForm: string;
  addedAt: number;
  /** Sách đã thêm mục này ("" khi thêm trong Cài đặt). */
  from: string;
  /** Cách cuốn đang xét đọc từ ấy (chỉ ở danh sách của một cuốn; "" khi chưa có). */
  current?: string;
}

export function useSharedReadings(enabled = true) {
  return useQuery({
    queryKey: ["shared-readings"],
    enabled,
    queryFn: () => api<{ entries: SharedReading[] }>("/api/readings"),
  });
}

/** Mục cách đọc chung của một từ (không phân biệt hoa thường); `reading` có thì chỉ khi mục ấy đọc ĐÚNG như vậy - dấu
 *  "dùng chung" trên dòng tên. */
export function useSharedEntry(surface: string, reading?: string | null, enabled = true): SharedReading | undefined {
  const { data } = useSharedReadings(enabled);
  const key = surface.toLocaleLowerCase("vi");
  return data?.entries.find(
    (entry) => entry.surface.toLocaleLowerCase("vi") === key && (reading == null || entry.spokenForm === reading),
  );
}

const SEARCH_FROM = 8;

/** Cài đặt → Studio: xem, thêm, bỏ cách đọc chung. */
export function SharedReadingsSettings() {
  const client = useQueryClient();
  const { data } = useSharedReadings();
  const [surface, setSurface] = useState("");
  const [spoken, setSpoken] = useState("");
  const [problem, setProblem] = useState("");
  const [filter, setFilter] = useState("");
  const [shown, setShown] = useState(12);
  const save = useMutation({
    mutationFn: (body: { surface: string; spokenForm?: string; remove?: boolean }) =>
      api<SharedReading | { removed: boolean }>("/api/readings", { method: "POST", body }),
    onSuccess: (_answer, body) => {
      void client.invalidateQueries({ queryKey: ["shared-readings"] });
      if (body.remove) {
        toast.success(`Đã bỏ “${body.surface}” khỏi cách đọc chung`);
        return;
      }
      setSurface("");
      setSpoken("");
      toast.success(`“${body.surface}” đọc là “${shownReading(body.spokenForm ?? "")}” cho mọi sách`);
    },
    onError: (error: Error) => setProblem(error.message),
  });
  const entries = data?.entries ?? [];
  const filtered = entries.filter((entry) => `${entry.surface} ${entry.spokenForm}`.toLocaleLowerCase("vi").includes(filter.toLocaleLowerCase("vi")));
  return (
    // Nằm trong khối gập "Cách đọc chung" của Cài đặt › Studio: lời dẫn trước, ô tìm chỉ khi danh sách đủ dài để cần tìm.
    <MotionRegion as="div" className="py-3">
      <p className="text-[0.8125rem] text-fg-2 text-pretty">Sửa cách đọc một tên một lần, sách mới tự dùng.</p>
      {entries.length > SEARCH_FROM && (
        <input aria-label="Tìm cách đọc" value={filter} onChange={(event) => { setFilter(event.target.value); setShown(12); }} className="mt-2 h-8 w-full rounded-control border border-line bg-panel px-2.5 text-sm outline-none focus-visible:border-focus" placeholder="Tìm tên…" />
      )}
      {/* Lọc / bỏ / thêm: hàng khép / mở tại chỗ; data-motion-live - khối không mờ lại cả theo từng phím gõ. */}
      <div data-motion-live="">
        <AnimatedRows className="mt-2 divide-y divide-line" items={filtered.slice(0, shown)} keyOf={(entry) => entry.surface}>
          {(entry) => (
            <div className="flex items-center gap-3 py-1.5 text-sm">
              <span className="min-w-0 flex-1 truncate">
                <span className="font-medium">{entry.surface}</span> <span className="text-fg-3">→</span> “{shownReading(entry.spokenForm)}”
                {entry.from && <span className="text-xs text-fg-3"> · từ {entry.from}</span>}
              </span>
              <IconButton
                label={`Bỏ “${entry.surface}” khỏi cách đọc chung`}
                icon={Trash2}
                onClick={() => save.mutate({ surface: entry.surface, remove: true })}
              />
            </div>
          )}
        </AnimatedRows>
      </div>
      <MotionPresence open={filtered.length > shown}><Button size="sm" variant="ghost" onClick={() => setShown(shown + 12)}>Xem thêm</Button></MotionPresence>
      <form
        className="mt-2 flex flex-wrap items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setProblem("");
          if (surface.trim() && spoken.trim()) save.mutate({ surface: surface.trim(), spokenForm: spoken.trim() });
        }}
      >
        <input
          id="shared-reading-surface"
          value={surface}
          onChange={(event) => setSurface(event.target.value)}
          placeholder="Từ trong sách, vd Nasdell"
          aria-label="Từ trong sách"
          autoComplete="off"
          spellCheck={false}
          className="h-8 w-56 max-w-full rounded-control border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-focus"
        />
        <input
          id="shared-reading-spoken"
          value={spoken}
          onChange={(event) => setSpoken(event.target.value)}
          placeholder="Đọc là, vd Hên-cơ"
          aria-label="Cách đọc"
          autoComplete="off"
          spellCheck={false}
          className="h-8 w-56 max-w-full rounded-control border border-line bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-focus"
        />
        <Button size="sm" variant="ghost" type="submit" loading={save.isPending} disabled={!surface.trim() || !spoken.trim()}>
          Thêm
        </Button>
      </form>
      {problem && <p className="mt-1 text-[0.8125rem] text-danger">{problem}</p>}
    </MotionRegion>
  );
}

/** Tab Nhân vật → Cách đọc tên của một cuốn: cách đọc chung có tên trong cuốn này mà cuốn đang đọc khác - một nút dùng hết. */
export function SharedReadingsOffer({ bookId }: { bookId: string }) {
  const client = useQueryClient();
  const { data } = useQuery({
    queryKey: ["shared-readings", bookId],
    queryFn: () => api<{ entries: SharedReading[] }>(`/api/books/${bookId}/shared-readings`),
  });
  const apply = useMutation({
    mutationFn: () => api<{ applied: string[] }>(`/api/books/${bookId}/shared-readings`, { method: "POST" }),
    onSuccess: ({ applied }) => {
      refreshAfterDecision(client, bookId);
      void client.invalidateQueries({ queryKey: ["shared-readings", bookId] });
      // Sách chưa thu câu nào (chưa bắt đầu, đang phân tích) thì không có gì để "thu lại" (soát UX 01-10).
      toast.success(`Đã dùng ${applied.length} cách đọc chung`);
    },
    onError: (error: Error) => toast.error("Chưa dùng được cách đọc chung", { description: error.message }),
  });
  const entries = data?.entries ?? [];
  if (!entries.length) return <MotionRegion />;
  // Cách cuốn đang đọc (nếu có) bên cạnh cách chung - người dùng thấy cái gì sẽ đổi thành cái gì.
  const shown = entries
    .slice(0, 3)
    .map((entry) =>
      entry.current
        ? `${entry.surface}: “${shownReading(entry.current)}” → “${shownReading(entry.spokenForm)}”`
        : `${entry.surface} → “${shownReading(entry.spokenForm)}”`,
    )
    .join(", ");
  return (
    <MotionRegion>
    <div className="mt-3 flex max-w-2xl flex-wrap items-center gap-3 py-2 text-sm">
      <span className="min-w-0 flex-1 text-pretty">
        Cách đọc chung khác cách cuốn này đang đọc: {shown}
        {entries.length > 3 ? `, và ${entries.length - 3} tên khác` : ""}
      </span>
      <Button size="sm" variant="ghost" icon={BookOpenCheck} loading={apply.isPending} onClick={() => apply.mutate()}>
        Dùng {entries.length} cách đọc chung
      </Button>
    </div>
    </MotionRegion>
  );
}
