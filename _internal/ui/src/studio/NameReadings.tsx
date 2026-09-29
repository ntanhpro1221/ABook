import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Search, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useClip } from "@/listen/clip";
import { cn } from "@/shared/cn";
import { formatNumber } from "@/shared/format";
import { Button } from "@/shared/ui";
import { api, urls } from "./api";

// Tab Nhân vật, mục "Cách đọc tên" (webui/name_readings.py): mọi tên riêng máy đọc thế nào - kể cả tên máy chắc và cách
// người nghe đã chọn, hai thứ hộp việc không bao giờ hỏi lại. Sửa ở đây đi đúng đường của thẻ cách đọc: ghi mong muốn,
// dây chuyền áp ở ranh giới chương và thu lại những câu có tên ấy.

interface NameReading {
  surface: string;
  spoken: string;
  /** Cách đọc đang nằm trong sách là người nghe chọn (không phải máy đoán). */
  byListener: boolean;
  lines: number;
  /** Cách đọc người nghe đã ghi mà dây chuyền chưa áp. */
  requested: string | null;
  example: { segmentId: number; chapterTitle: string; seq: number; text: string; hasAudio: boolean } | null;
}

const PAGE = 30;

function useNameReadings(bookId: string) {
  return useQuery({
    queryKey: ["pronunciations", bookId],
    queryFn: () => api<{ items: NameReading[]; unseen: number }>(`/api/books/${bookId}/pronunciations`),
  });
}

/** So tên không phân biệt hoa thường và dấu: gõ "hen" thấy "Hên-cơ". */
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

export function NameReadings({ bookId }: { bookId: string }) {
  const { data } = useNameReadings(bookId);
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(PAGE);
  if (!data || (!data.items.length && !data.unseen)) return null;
  const typed = query.trim();
  const needle = fold(typed);
  const found = needle
    ? data.items.filter((item) => fold(item.surface).includes(needle) || fold(item.requested ?? item.spoken).includes(needle))
    : data.items;
  // Tên chưa có dòng nào (máy không coi là tên riêng, hay chưa gặp): gõ đúng một từ thì thêm được cách đọc cho nó.
  const addable = /^[\p{L}\p{M}'’-]+$/u.test(typed) && !data.items.some((item) => fold(item.surface) === needle);
  return (
    <section className="mt-8" aria-labelledby="name-readings-title">
      <h3 id="name-readings-title" className="text-sm font-semibold">
        Cách đọc tên <span className="font-normal text-fg-2">· {formatNumber(data.items.length)} tên trong phần này</span>
      </h3>
      <p className="mt-1 max-w-prose text-sm text-fg-2">
        Tên riêng máy đọc thế nào. Nghe câu mẫu, sai thì sửa ngay trên dòng - các câu có tên ấy sẽ được thu lại.
      </p>
      <div className="relative mt-3 max-w-sm">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-3" aria-hidden />
        <input
          id="name-readings-search"
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setLimit(PAGE);
          }}
          placeholder="Tìm tên, hoặc gõ một tên để thêm cách đọc"
          aria-label="Tìm tên"
          autoComplete="off"
          spellCheck={false}
          className="h-9 w-full rounded-lg border border-line bg-panel pl-8 pr-8 text-sm outline-none focus-visible:border-accent [&::-webkit-search-cancel-button]:hidden"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Xoá ô tìm"
            className="absolute right-1.5 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded-md text-fg-3 hover:text-fg"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
      {(found.length > 0 || addable) && (
        <ul className="mt-3 divide-y divide-line rounded-xl border border-line bg-panel">
          {found.slice(0, limit).map((item) => (
            <ReadingRow key={item.surface} bookId={bookId} item={item} />
          ))}
          {addable && <ReadingRow key={`new-${typed}`} bookId={bookId} item={{ surface: typed, spoken: "", byListener: false, lines: 0, requested: null, example: null }} fresh />}
        </ul>
      )}
      {!found.length && !addable && typed && <p className="mt-3 text-sm text-fg-2">Không có tên nào khớp “{typed}”.</p>}
      {found.length > limit && (
        <button type="button" onClick={() => setLimit((value) => value + PAGE * 3)} className="mt-3 text-sm font-medium text-fg-2 hover:text-fg">
          Xem thêm {formatNumber(found.length - limit)} tên
        </button>
      )}
      {data.unseen > 0 && !typed && (
        <p className="mt-2 text-xs text-fg-3">{formatNumber(data.unseen)} tên khác của cuốn không có câu nào trong phần này.</p>
      )}
    </section>
  );
}

function ReadingRow({ bookId, item, fresh = false }: { bookId: string; item: NameReading; fresh?: boolean }) {
  const clip = useClip();
  const [editing, setEditing] = useState(fresh);
  const example = item.example;
  const id = example ? `reading-${example.segmentId}` : "";
  const playing = Boolean(id) && clip.current === id;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
      {example?.hasAudio ? (
        <button
          type="button"
          onClick={() => clip.toggle(id, urls.sample(bookId, example.segmentId))}
          aria-label={playing ? "Dừng" : `Nghe câu có ${item.surface}: ${example.text}`}
          title={`${example.chapterTitle} · câu ${example.seq}`}
          className="grid size-8 shrink-0 place-items-center rounded-full bg-hover text-fg-2 hover:text-fg"
        >
          {playing ? <Pause className="size-3.5" fill="currentColor" strokeWidth={0} /> : <Play className="size-3.5 translate-x-[1px]" fill="currentColor" strokeWidth={0} />}
        </button>
      ) : (
        <span className="size-8 shrink-0" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-1.5">
          <span className="font-semibold">{item.surface}</span>
          {item.spoken && (
            <>
              <span className="text-sm text-fg-2">đọc là</span>
              <span className="whitespace-nowrap font-medium">“{item.spoken}”</span>
            </>
          )}
        </div>
        <div className="tabular text-xs text-fg-2">
          {fresh
            ? "Chưa có cách đọc riêng - máy đọc theo chữ"
            : `${formatNumber(item.lines)} câu · ${item.byListener ? "đã chọn" : item.spoken ? "máy đoán" : "chưa có trong sách"}`}
          {item.requested && (
            <span className="font-medium text-accent-text">
              {" "}
              · chờ áp dụng: <span className="whitespace-nowrap">“{item.requested}”</span>
            </span>
          )}
        </div>
      </div>
      {editing ? (
        <EditReading bookId={bookId} item={item} onDone={() => setEditing(false)} fresh={fresh} />
      ) : (
        <Button size="sm" variant="ghost" onClick={() => setEditing(true)} aria-label={`Sửa cách đọc ${item.surface}`}>
          Sửa
        </Button>
      )}
    </li>
  );
}

function EditReading({ bookId, item, onDone, fresh }: { bookId: string; item: NameReading; onDone: () => void; fresh: boolean }) {
  const client = useQueryClient();
  const [value, setValue] = useState(item.requested ?? item.spoken);
  const [problem, setProblem] = useState("");
  const save = useMutation({
    mutationFn: (spokenForm: string) =>
      api<{ surface: string; spokenForm: string }>(`/api/books/${bookId}/pronunciation`, {
        method: "POST",
        body: { surface: item.surface, spokenForm },
      }),
    onSuccess: ({ spokenForm }) => {
      void client.invalidateQueries({ queryKey: ["pronunciations", bookId] });
      void client.invalidateQueries({ queryKey: ["work", bookId] });
      void client.invalidateQueries({ queryKey: ["book", bookId] });
      void client.invalidateQueries({ queryKey: ["library"] });
      onDone();
      if (spokenForm === item.spoken) {
        toast.success(`Giữ cách đọc "${spokenForm}"`, { description: "Không phải thu lại câu nào." });
        return;
      }
      toast.success(`Đã ghi: "${item.surface}" đọc là "${spokenForm}"`, {
        description: "Các câu có tên này sẽ được thu lại. Thu lại khi sách chạy tiếp - sách đã xong thì bấm “Áp dụng thay đổi” ở trang dự án.",
      });
    },
    onError: (error: Error) => setProblem(error.message),
  });
  const typed = value.trim();
  const inputId = `reading-${fold(item.surface)}`;
  return (
    <form
      className="flex w-full flex-wrap items-center gap-2 sm:w-auto"
      onSubmit={(event) => {
        event.preventDefault();
        if (typed) save.mutate(typed);
      }}
    >
      <input
        id={inputId}
        autoFocus
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
          setProblem("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") onDone();
        }}
        placeholder="vd Hên-khơ"
        aria-label={`Cách đọc mới cho ${item.surface}`}
        aria-invalid={problem ? true : undefined}
        aria-describedby={problem ? `${inputId}-problem` : undefined}
        spellCheck={false}
        autoComplete="off"
        className={cn(
          "h-8 min-w-0 flex-1 rounded-lg border bg-panel px-2.5 text-sm text-fg outline-none focus-visible:border-accent sm:w-44 sm:flex-none",
          problem ? "border-danger" : "border-line",
        )}
      />
      <Button size="sm" variant="primary" type="submit" loading={save.isPending} disabled={!typed || (!fresh && typed === (item.requested ?? item.spoken))}>
        Lưu
      </Button>
      <Button size="sm" variant="ghost" type="button" onClick={onDone}>
        Huỷ
      </Button>
      {problem && (
        <p id={`${inputId}-problem`} role="alert" className="w-full text-xs text-danger">
          {problem}
        </p>
      )}
    </form>
  );
}
