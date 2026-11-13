import { S } from "../shared/strings.generated";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lightbulb } from "lucide-react";
import { useState } from "react";
import { toast } from "@/shared/toast";
import { BOOK_STORAGE } from "@/shared/bookStorage";
import { OnComputerOnly } from "@/shared/OnComputerOnly";
import { MotionPresence, Reveal } from "@/shared/MotionPresence";
import { MotionRegion } from "@/shared/MotionRegion";
import { DialogActions, Button, Dialog, IconButton } from "@/shared/ui";
import { api } from "@/studio/api";
import { useAppInfo } from "@/studio/data";
import { refreshAfterEdit } from "./EditBook";
import type { ListenBook } from "./model";
import { SlotFace, useMenuSlot } from "./menuSlot";
import { usePlayer } from "./player";

// Gợi ý của bộ nhập sách cho phần ĐỌC (dòng ghi công của người dịch / biên tập ở đầu chương, lời xin ủng hộ / nguồn ở cuối chương): người nghe chọn bỏ dòng nào khỏi phần
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
  return chapters.length === 1 ? S.s_chuong_0_55d256d1(chapters[0]) : S.s_0_chuong_04093412(chapters.length);
}

/** Các gợi ý, mỗi dòng một ô "Bỏ đọc dòng" (cùng chữ với điện thoại, addbook/AddBookScreen.kt). */
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
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              checked={isOn(group)}
              disabled={disabled}
              onChange={(event) => onChange(group, event.target.checked)}
              className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
            />
            <span className="min-w-0">
              <span className="block">{S.s_bo_doc_dong_3e82a7fd}</span>
              <span className="block break-words text-xs text-fg-2">
                “{group.line}” · {where(group.chapters)}
              </span>
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}

// "Bỏ qua gợi ý": người nghe đã xem và quyết giữ nguyên - thẻ ở trang sách thôi đếm "N chưa áp" và thu lại (soát a70: thẻ nằm mãi). Nhớ trên máy
// này theo từng dòng: gợi ý MỚI (dòng chưa từng bỏ qua) vẫn hiện lại. Mặc định vẫn không áp gì.
const DISMISSED_KEY = BOOK_STORAGE.suggestionsDismissed;

function dismissedLines(bookId: string): string[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(DISMISSED_KEY + bookId) ?? "[]");
    return Array.isArray(value) ? value.filter((line): line is string => typeof line === "string") : [];
  } catch {
    return [];
  }
}

/** Gợi ý của một cuốn + đổi lựa chọn + bỏ qua (dùng chung cho thẻ ở trang sách và hộp mở từ trình phát). */
function useBookSuggestions(bookId: string, enabled = true) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["book", bookId, "suggestions"],
    queryFn: () => api<{ suggestions: Suggestion[] }>(`/api/books/${bookId}/suggestions`),
    staleTime: 60_000,
    enabled: enabled && Boolean(bookId),
    retry: false,
  });
  const toggle = useMutation({
    mutationFn: ({ group, on }: { group: SuggestionGroup; on: boolean }) => setSkipLine(bookId, group.line, group.chapters, on),
    onSuccess: async () => {
      void client.invalidateQueries({ queryKey: ["book", bookId, "suggestions"] });
      // Sách (kèm `skip` của từng chương) phải mới TRƯỚC, rồi mới bỏ kịch bản đã dựng: màn đọc mở ngay sau cú tích mà còn thấy sách cũ thì dựng lại kịch
      // bản theo `skip` cũ và giữ nó mãi (staleTime vô hạn).
      await client.refetchQueries({ queryKey: ["listen", "book", bookId] }).catch(() => undefined);
      // Các đoạn của chương đổi: bỏ kịch bản chữ đã dựng (khoá ["listen", "script", …]) cùng mọi thứ của trang nghe.
      client.removeQueries({ queryKey: ["listen", "script", bookId] });
      refreshAfterEdit(client, bookId);
    },
    onError: (error) => toast.error(S.s_chua_doi_duoc_phan_doc_c573a0df, { description: (error as Error).message }),
  });
  const [dismissed, setDismissed] = useState(() => dismissedLines(bookId));
  const groups = groupSuggestions(query.data?.suggestions ?? []);
  const pending = groups.filter((group) => !group.skipped && !dismissed.includes(group.line));
  const dismiss = () => {
    const next = [...new Set([...dismissed, ...groups.filter((group) => !group.skipped).map((group) => group.line)])];
    setDismissed(next);
    try {
      window.localStorage.setItem(DISMISSED_KEY + bookId, JSON.stringify(next));
    } catch {
      // không nhớ được thì lần mở sau thẻ hiện lại - không sao
    }
  };
  return { groups, pending: pending.length, toggle, dismiss };
}

/** Lời giải thích + các ô chọn của gợi ý (thẻ ở trang sách, hộp ở trình phát). */
function SuggestionsBody({ bookId, suggestions }: { bookId: string; suggestions: ReturnType<typeof useBookSuggestions> }) {
  const { track } = usePlayer();
  // Thiết bị chỉ được nghe: thấy gợi ý nhưng không bỏ dòng được - việc ấy ở máy tính.
  const { data: info } = useAppInfo();
  const listenOnly = Boolean(info?.listenOnly);
  const { groups, toggle } = suggestions;
  return (
    <>
      <p className="mt-1 text-xs text-fg-2 text-pretty">{S.s_bo_khoi_phan_doc_giu_chu_goc_bo_chon_de_do_35421485}{track?.bookId === bookId && S.s_chuong_dang_nghe_se_doi_tu_lan_nghe_sau_ca_06a20d3f}
      </p>
      <div className="mt-2">
        <SuggestionChoices
          groups={groups}
          isOn={(group) => group.skipped}
          disabled={toggle.isPending || listenOnly}
          onChange={(group, on) => toggle.mutate({ group, on })}
        />
        <Reveal when={listenOnly}><p className="mt-2">
            <OnComputerOnly verb={S.s_bo_dong_khoi_phan_doc_7b69e049} />
          </p></Reveal>
      </div>
    </>
  );
}

/** Trang sách (cuốn chỉ-có-chữ sửa được): gợi ý còn chờ và gợi ý đã áp, chọn / bỏ chọn được bất cứ lúc nào. Đã "Bỏ qua gợi ý" (và không còn
 *  gợi ý mới) thì thẻ thu lại thành một dòng mở lại được. */
export function BookSuggestions({ book }: { book: ListenBook }) {
  const suggestions = useBookSuggestions(book.id);
  const [open, setOpen] = useState(false);
  const { groups, pending, dismiss } = suggestions;
  const quiet = !pending && !groups.some((group) => group.skipped);
  // Khối tự lấy dữ liệu nên tự mang chuyển động (vùng cha không thấy truy vấn này): có / không gợi ý mở / khép tại chỗ, đổi thẻ <-> dòng
  // "Xem lại gợi ý" mờ qua.
  return (
    <MotionPresence open={groups.length > 0}>
      <MotionRegion motionKey={quiet && !open ? "quiet" : "card"}>
        {quiet && !open ? (
          <button type="button" onClick={() => setOpen(true)} className="mt-3 text-left text-xs font-medium text-accent-text hover:underline">{S.s_xem_lai_goi_y_fd8e89c7}</button>
        ) : (
          <section className="mt-4 max-w-xl py-3 text-left">
            <h2 className="text-sm font-medium">
              <MotionRegion as="span">{S.s_goi_y_phan_doc_b268d95e}{pending ? S.s_0_chua_ap_85970233(pending) : ""}</MotionRegion>
            </h2>
            <SuggestionsBody bookId={book.id} suggestions={suggestions} />
            <MotionPresence open={pending > 0}>
              <Button size="sm" variant="ghost" className="mt-2" onClick={() => {
                dismiss();
                setOpen(false);
              }}>{S.s_bo_qua_goi_y_bccec2b3}</Button>
            </MotionPresence>
          </section>
        )}
      </MotionRegion>
    </MotionPresence>
  );
}

/** Nút ở trình phát (soát a70: gợi ý chỉ có ở trang sách): cuốn đang phát có gợi ý thì mở được hộp gợi ý ngay tại đây. */
export function SuggestionsButton({ bookId, className }: { bookId: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const slot = useMenuSlot();
  const suggestions = useBookSuggestions(bookId);
  const { groups, pending, dismiss } = suggestions;
  if (!groups.length) return null;
  const label = pending ? S.s_goi_y_cho_phan_doc_0_chua_ap_700c648b(pending) : S.s_goi_y_phan_doc_b268d95e;
  return (
    <>
      {slot
        ? <SlotFace aria-label={label} value={pending ? S.s_0_chua_ap_0ddead2d(pending) : S.s_xem_f6de0ffd} onClick={() => setOpen(true)} />
        : <IconButton label={label} icon={Lightbulb} size="sm" className={className} onClick={() => setOpen(true)} />}
      <Dialog footer={<DialogActions>
          <Reveal when={pending > 0}><Button variant="ghost" onClick={() => {
              dismiss();
              setOpen(false);
            }}>{S.s_bo_qua_goi_y_bccec2b3}</Button></Reveal>
          <Button variant="ghost" onClick={() => setOpen(false)}>{S.s_dong_5d54c2a1}</Button>
        </DialogActions>} open={open} onOpenChange={setOpen} title={S.s_goi_y_phan_doc_b268d95e}>
        <SuggestionsBody bookId={bookId} suggestions={suggestions} />
        {/* Tích hết dòng lúc hộp còn mở: "Bỏ qua gợi ý" rời hàng nút bằng mờ qua, không mất cứng. */}

      </Dialog>
    </>
  );
}
