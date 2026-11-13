import { S } from "../shared/strings.generated";
import { MotionRegion } from "@/shared/MotionRegion";
import { AnimatedRows, MotionPresence, Reveal } from "@/shared/MotionPresence";
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
        toast.success(S.s_da_bo_0_khoi_cach_doc_chung_77f7c603(body.surface));
        return;
      }
      setSurface("");
      setSpoken("");
      toast.success(S.s_0_doc_la_1_cho_moi_sach_35251e6e(body.surface, shownReading(body.spokenForm ?? "")));
    },
    onError: (error: Error) => setProblem(error.message),
  });
  const entries = data?.entries ?? [];
  const filtered = entries.filter((entry) => `${entry.surface} ${entry.spokenForm}`.toLocaleLowerCase("vi").includes(filter.toLocaleLowerCase("vi")));
  return (
    // Nằm trong khối gập "Cách đọc chung" của Cài đặt › Studio: lời dẫn trước, ô tìm chỉ khi danh sách đủ dài để cần tìm.
    <MotionRegion as="div" className="py-3">
      <p className="text-body-small text-fg-2 text-pretty">{S.s_sua_cach_doc_mot_ten_mot_lan_sach_moi_tu_d_f1569d6e}</p>
      {entries.length > SEARCH_FROM && (
        <input aria-label={S.s_tim_cach_doc_690f3c7e} value={filter} onChange={(event) => { setFilter(event.target.value); setShown(12); }} className="mt-2 h-8 w-full rounded-control border border-line bg-panel px-3 text-sm outline-none focus-visible:border-focus" placeholder={S.s_tim_ten_260c6baf} />
      )}
      {/* Lọc / bỏ / thêm: hàng khép / mở tại chỗ; data-motion-live - khối không mờ lại cả theo từng phím gõ. */}
      <div data-motion-live="">
        <AnimatedRows className="mt-2 divide-y divide-line" items={filtered.slice(0, shown)} keyOf={(entry) => entry.surface}>
          {(entry) => (
            <div className="flex items-center gap-3 py-2 text-sm">
              <span className="min-w-0 flex-1 truncate">
                <span className="font-medium">{entry.surface}</span> <span className="text-fg-3">→</span> “{shownReading(entry.spokenForm)}”
                <Reveal when={entry.from}><span className="text-xs text-fg-3">{S.s_tu_02926cd1}{entry.from}</span></Reveal>
              </span>
              <IconButton
                label={S.s_bo_cach_doc_0_a883978b(entry.surface)}
                icon={Trash2}
                onClick={() => save.mutate({ surface: entry.surface, remove: true })}
              />
            </div>
          )}
        </AnimatedRows>
      </div>
      <MotionPresence open={filtered.length > shown}><Button size="sm" variant="ghost" onClick={() => setShown(shown + 12)}>{S.s_xem_them_e0ac1b1e}</Button></MotionPresence>
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
          placeholder={S.s_tu_trong_sach_vd_nasdell_e5609228}
          aria-label={S.s_tu_trong_sach_e93bdaec}
          autoComplete="off"
          spellCheck={false}
          className="h-8 w-56 max-w-full rounded-control border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-focus"
        />
        <input
          id="shared-reading-spoken"
          value={spoken}
          onChange={(event) => setSpoken(event.target.value)}
          placeholder={S.s_doc_la_vd_hen_co_6e778b3d}
          aria-label={S.s_cach_doc_94265da7}
          autoComplete="off"
          spellCheck={false}
          className="h-8 w-56 max-w-full rounded-control border border-line bg-panel px-3 text-sm text-fg outline-none focus-visible:border-focus"
        />
        <Button size="sm" variant="ghost" type="submit" loading={save.isPending} disabled={!surface.trim() || !spoken.trim()}>{S.s_them_dd92626f}</Button>
      </form>
      {problem && <p className="mt-1 text-body-small text-danger">{problem}</p>}
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
      toast.success(S.s_da_dung_0_cach_doc_chung_f3c4cdb8(applied.length));
    },
    onError: (error: Error) => toast.error(S.s_chua_dung_duoc_cach_doc_chung_cb8d8746, { description: error.message }),
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
      <span className="min-w-0 flex-1 text-pretty">{S.s_cach_doc_chung_khac_cach_cuon_nay_dang_doc_82c45e55}{shown}
        {entries.length > 3 ? S.s_va_0_ten_khac_27b80d61(entries.length - 3) : ""}
      </span>
      <Button size="sm" variant="ghost" icon={BookOpenCheck} loading={apply.isPending} onClick={() => apply.mutate()}>{S.s_dung_5c3730f4}{entries.length}{S.s_cach_doc_chung_c315f242}</Button>
    </div>
    </MotionRegion>
  );
}
