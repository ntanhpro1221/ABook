import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronRight, Music2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { api } from "@/studio/api";
import { MUSIC_CHANGED_EVENT } from "./musicBed";
import { playlistOptions, savePlaylistChoice, type PlaylistMenu, type PlaylistOption } from "./playlistBed";

// "Nhạc nền" của sách chỉ có chữ (playlistBed.ts): chọn ở menu của sách và ở trình phát - cùng một lựa chọn, lưu vào phần sửa của
// sách nên đi theo sách. Máy tính hỏi máy chủ, điện thoại hỏi lõi native qua cùng đường (android/localStudio.ts).

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

/** Danh sách phát người nghe đã chọn cho cuốn `bookId` + các lựa chọn + cách đổi. `enabled` false: chưa hỏi gì (menu chưa mở). */
export function usePlaylistChoice(bookId: string, enabled = true) {
  const client = useQueryClient();
  const key = ["listen", "edit-music", bookId];
  const menu = useQuery({
    queryKey: ["music", "playlists"],
    queryFn: () => api<PlaylistMenu>("/api/music/playlists"),
    staleTime: 10 * 60_000,
    enabled,
  });
  const current = useQuery({ queryKey: key, queryFn: () => api<{ playlist?: string }>(`/api/books/${bookId}/music`), enabled });
  const choose = useMutation({
    mutationFn: (playlist: string | null) => savePlaylistChoice(bookId, playlist),
    onSuccess: (view, playlist) => {
      // Chọn xong phải thấy đã đổi (menu đóng ngay): nói tên danh sách vừa chọn.
      const name = playlist === null ? "Tắt" : playlistOptions(menu.data).find((option) => option.id === playlist)?.label;
      if (name) toast(`Nhạc nền: ${name}`, { id: "playlist-choice", duration: 2500 });
      client.setQueryData(key, view);
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] }); // số thay đổi của cuốn
      void client.invalidateQueries({ queryKey: ["listen", "library"] });
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error) => toast.error("Chưa đổi được nhạc nền", { description: error.message }),
  });
  return {
    options: playlistOptions(menu.data),
    chosen: current.data?.playlist ?? null,
    error: menu.data?.error ?? "",
    loading: menu.isLoading,
    choose: (id: string | null) => choose.mutate(id),
  };
}

/** Một dòng lựa chọn: tên, độ dài (hay số bài), dấu đang chọn; mô tả danh sách ở dòng nhỏ dưới. */
export function PlaylistOptionLabel({ option, chosen }: { option: PlaylistOption; chosen: boolean }) {
  return (
    <>
      <Check className={cn("size-4 shrink-0", chosen ? "text-accent-text" : "invisible")} />
      <span className="min-w-0 flex-1">
        <span className="block text-pretty">{option.label}</span>
        {option.description && <span className="block text-pretty text-xs font-normal text-fg-3">{option.description}</span>}
      </span>
      {option.hint && <span className="shrink-0 text-xs font-normal text-fg-2">{option.hint}</span>}
    </>
  );
}

/** Chữ nhỏ dưới các lựa chọn: điều người nghe cần biết (mất mạng lần đầu thì lý do). */
export function playlistNote(error: string): string {
  return error || "Nhạc nằm dưới giọng đọc và nghe tiếp qua các chương. Lần đầu cần mạng để tải bài.";
}

/** Mục "Nhạc nền" trong menu của sách chỉ có chữ: menu con với các lựa chọn. */
export function PlaylistSubmenu({ bookId }: { bookId: string }) {
  const { options, chosen, error, loading, choose } = usePlaylistChoice(bookId);
  const current = options.find((option) => option.id === chosen);
  return (
    <DropdownMenu.Sub>
      <DropdownMenu.SubTrigger className={MENU_ITEM}>
        <Music2 className="size-4" />
        <span className="flex-1">Nhạc nền</span>
        <span className="max-w-28 truncate text-xs text-fg-2">{current?.label ?? "Tắt"}</span>
        <ChevronRight className="size-4 text-fg-2" />
      </DropdownMenu.SubTrigger>
      <DropdownMenu.Portal>
        <DropdownMenu.SubContent sideOffset={4} collisionPadding={12} className="z-50 max-h-[70vh] w-72 overflow-y-auto rounded-xl border border-line bg-panel p-1.5 shadow-float">
          {options.map((option) => (
            <DropdownMenu.Item
              key={option.id ?? "off"}
              disabled={option.disabled}
              onSelect={() => choose(option.id)}
              className={cn(MENU_ITEM, "h-auto min-h-9 py-1.5 data-[disabled]:opacity-50", option.id === chosen && "font-semibold")}
            >
              <PlaylistOptionLabel option={option} chosen={option.id === chosen} />
            </DropdownMenu.Item>
          ))}
          {loading && <p className="px-2 py-1.5 text-xs text-fg-2">Đang tải các danh sách nhạc…</p>}
          <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{playlistNote(error)}</p>
        </DropdownMenu.SubContent>
      </DropdownMenu.Portal>
    </DropdownMenu.Sub>
  );
}
