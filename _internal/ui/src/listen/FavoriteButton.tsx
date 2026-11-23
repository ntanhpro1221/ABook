import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import { toast } from "@/shared/toast";
import { S } from "../shared/strings.generated";
import { ActionButton } from "./ActionButton";
import type { ListenBook } from "./model";
import { isRecordGone, RECORD_GONE_MESSAGE, shownRecord } from "./recordWrites";
import { useSource } from "./source";

/** Thả / bỏ tim cho cuốn: trang sách, màn Đang nghe và thư viện dùng chung. Khoá bấm lặp khi đang ghi; trạng thái đích hiện sau kết quả thật
 *  (DESIGN "Thao tác phải chờ") - trạng thái máy chủ trả về vào ngay bộ đệm cuốn và thư viện, rồi mới hỏi lại. */
export function useFavoriteToggle(bookId: string | undefined) {
  const source = useSource();
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (favorite: boolean) => source.setFavorite(bookId!, favorite, shownRecord(client, bookId!)),
    onSuccess: (state) => {
      const merge = (book: ListenBook | undefined) => (book && book.id === bookId ? { ...book, state: { ...book.state, favorite: state.favorite, favoriteAt: state.favoriteAt } } : book);
      client.setQueryData<ListenBook>(["listen", "book", bookId], merge);
      client.setQueryData<ListenBook[]>(["listen", "library"], (books) => books?.map((book) => merge(book)!));
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
      void client.invalidateQueries({ queryKey: ["listen", "library"] });
    },
    onError: (error) => {
      if (!isRecordGone(error)) return;
      toast.error(RECORD_GONE_MESSAGE, { id: "record-gone" });
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
    },
  });
  return (favorite: boolean) => {
    if (!bookId || mutation.isPending) return;
    mutation.mutate(favorite);
  };
}

/** Hình tim của trạng thái yêu thích: viền khi chưa thả, tô đầy màu nhấn khi đã thả (cùng một hình ở nút, ô thư viện). */
export function HeartGlyph({ on, className = "size-5" }: { on: boolean; className?: string }) {
  return <Heart aria-hidden className={className} strokeWidth={2} fill={on ? "currentColor" : "none"} />;
}

/** Nút tim trong hàng nút phụ có nhãn (trang sách, màn Đang nghe). Đổi icon bằng mờ chéo + co 0,8 → 1 tại ô (StateIcon của ActionButton). */
export function FavoriteButton({ bookId, on }: { bookId: string; on: boolean }) {
  const toggle = useFavoriteToggle(bookId);
  return (
    <ActionButton
      data-favorite={on ? "on" : "off"}
      glyph={<HeartGlyph on={on} />}
      glyphKey={on}
      label={S.s_heart_favorite}
      aria-label={on ? S.s_heart_unfavorite : S.s_heart_favorite}
      active={on}
      onClick={() => toggle(!on)}
    />
  );
}
