import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/studio/api";
import { refreshAfterEdit } from "./EditBook";
import type { ListenBook } from "./model";
import { usePlayer } from "./player";

// Gợi ý của bộ nhập sách cho phần ĐỌC (dòng ghi công của người dịch / biên tập ở đầu chương): người nghe chọn bỏ dòng nào khỏi phần
// đọc - màn đọc và giọng đọc bỏ qua nó (lớp sửa `skip`, listen/textScript.ts `withoutLines`), chữ của truyện trong sách KHÔNG đổi, bỏ
// chọn là đọc lại như cũ. Mặc định không bỏ gì. Một dòng hay lặp ở đầu cả trăm chương ("Trans: …"): gộp lại, một lần chọn.

export interface Suggestion {
  chapter: number;
  line: string;
  /** Đang bỏ khỏi phần đọc (trang sách); bước xem trước thì chưa có sách nên không có. */
  skipped?: boolean;
}

export interface SuggestionGroup {
  line: string;
  chapters: number[];
  /** Mọi chương mang dòng này đều đang bỏ nó. */
  skipped: boolean;
}

export function groupSuggestions(items: readonly Suggestion[]): SuggestionGroup[] {
  const groups = new Map<string, { chapters: number[]; skipped: boolean }>();
  for (const item of items) {
    const group = groups.get(item.line) ?? { chapters: [], skipped: true };
    group.chapters.push(item.chapter);
    group.skipped &&= item.skipped === true;
    groups.set(item.line, group);
  }
  return [...groups].map(([line, group]) => ({ line, ...group }));
}

/** Bỏ (hay đọc lại) dòng `line` trong phần đọc của các chương ấy (`PUT /api/books/<mã>/skip`; điện thoại: LocalStudio). */
export function setSkipLine(bookId: string, line: string, chapters: number[], skip: boolean) {
  return api<{ skip: Record<string, string[]> }>(`/api/books/${bookId}/skip`, { method: "PUT", body: { line, chapters, skip } });
}

function where(chapters: number[]): string {
  return chapters.length === 1 ? `đầu chương ${chapters[0]}` : `đầu ${chapters.length} chương`;
}

/** Các gợi ý, mỗi dòng một ô "Bỏ dòng này khỏi phần đọc". */
export function SuggestionChoices({ groups, isOn, onChange, disabled }: {
  groups: SuggestionGroup[];
  isOn: (group: SuggestionGroup) => boolean;
  onChange: (group: SuggestionGroup, on: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <ul className="space-y-2">
      {groups.map((group) => (
        <li key={group.line}>
          <label className="flex items-start gap-2.5 text-sm">
            <input
              type="checkbox"
              checked={isOn(group)}
              disabled={disabled}
              onChange={(event) => onChange(group, event.target.checked)}
              className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
            />
            <span className="min-w-0">
              <span className="block">Bỏ dòng này khỏi phần đọc</span>
              <span className="block break-words text-xs text-fg-2">
                “{group.line}” - {where(group.chapters)}
              </span>
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}

/** Trang sách (cuốn chỉ-có-chữ sửa được): gợi ý còn chờ và gợi ý đã áp, chọn / bỏ chọn được bất cứ lúc nào. */
export function BookSuggestions({ book }: { book: ListenBook }) {
  const client = useQueryClient();
  const { track } = usePlayer();
  const query = useQuery({
    queryKey: ["book", book.id, "suggestions"],
    queryFn: () => api<{ suggestions: Suggestion[] }>(`/api/books/${book.id}/suggestions`),
    staleTime: 60_000,
  });
  const toggle = useMutation({
    mutationFn: ({ group, on }: { group: SuggestionGroup; on: boolean }) => setSkipLine(book.id, group.line, group.chapters, on),
    onSuccess: async () => {
      void client.invalidateQueries({ queryKey: ["book", book.id, "suggestions"] });
      // Sách (kèm `skip` của từng chương) phải mới TRƯỚC, rồi mới bỏ kịch bản đã dựng: màn đọc mở ngay sau cú tích mà còn thấy sách cũ thì dựng lại kịch
      // bản theo `skip` cũ và giữ nó mãi (staleTime vô hạn).
      await client.refetchQueries({ queryKey: ["listen", "book", book.id] }).catch(() => undefined);
      // Các đoạn của chương đổi: bỏ kịch bản chữ đã dựng (khoá ["listen", "script", …]) cùng mọi thứ của trang nghe.
      client.removeQueries({ queryKey: ["listen", "script", book.id] });
      refreshAfterEdit(client, book.id);
    },
    onError: (error) => toast.error("Chưa đổi được phần đọc", { description: (error as Error).message }),
  });
  const groups = groupSuggestions(query.data?.suggestions ?? []);
  if (!groups.length) return null;
  const pending = groups.filter((group) => !group.skipped).length;
  return (
    <section className="mt-4 max-w-xl rounded-xl border border-line bg-hover p-3 text-left">
      <h2 className="text-sm font-medium">
        Gợi ý cho phần đọc{pending ? ` · ${pending} chưa áp` : ""}
      </h2>
      <p className="mt-0.5 text-xs text-fg-2 text-pretty">
        Dòng ghi công của người dịch, biên tập ở đầu chương. Bỏ dòng này chỉ khiến màn đọc và giọng đọc bỏ qua nó - chữ của sách vẫn giữ
        nguyên, bỏ chọn là đọc lại.
        {track?.bookId === book.id && " Chương đang nghe sẽ đổi từ lần nghe sau; các chương khác đổi ngay."}
      </p>
      <div className="mt-2">
        <SuggestionChoices
          groups={groups}
          isOn={(group) => group.skipped}
          disabled={toggle.isPending}
          onChange={(group, on) => toggle.mutate({ group, on })}
        />
      </div>
    </section>
  );
}
