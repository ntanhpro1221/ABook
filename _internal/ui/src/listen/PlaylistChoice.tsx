import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronRight, Music2, Plus } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/shared/cn";
import { api } from "@/studio/api";
import { importMusic } from "@/studio/musicImport";
import { MY_MUSIC_KEY, useCanImportMusic } from "./MyMusic";
import { MUSIC_CHANGED_EVENT } from "./musicBed";
import { ADD_MUSIC_LABEL, addMusicOutcome, MINE_PLAYLIST, playlistOptions, savePlaylistChoice, type PlaylistMenu, type PlaylistOption } from "./playlistBed";

// "Nhạc nền" của sách chỉ có chữ (playlistBed.ts): chọn ở menu của sách và ở trình phát - cùng một lựa chọn, lưu vào phần sửa của
// sách nên đi theo sách. Máy tính hỏi máy chủ, điện thoại hỏi lõi native qua cùng đường (android/localStudio.ts).

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

const ADD_TOAST = "music-add";
/** Một lượt thêm nhạc tại một thời điểm: hộp chọn file đang mở / đang chép thì bấm nữa không mở thêm. Ở mức module vì menu đóng lại
 *  (hook gỡ ra) mà lượt thêm vẫn chạy tiếp. */
let adding = false;

/** Danh sách phát người nghe đã chọn cho cuốn `bookId` + các lựa chọn + cách đổi. `enabled` false: chưa hỏi gì (menu chưa mở).
 *  `canImport`/`addMusic`: thêm nhạc của mình ngay từ menu (máy nhập được nhạc), xong thì chọn "Nhạc của tôi" cho cuốn này. */
export function usePlaylistChoice(bookId: string, enabled = true) {
  const client = useQueryClient();
  const key = ["listen", "edit-music", bookId];
  const canImport = useCanImportMusic();
  const menu = useQuery({
    queryKey: ["music", "playlists"],
    queryFn: () => api<PlaylistMenu>("/api/music/playlists"),
    staleTime: 10 * 60_000,
    enabled,
  });
  const current = useQuery({ queryKey: key, queryFn: () => api<{ playlist?: string }>(`/api/books/${bookId}/music`), enabled });
  const chosen = current.data?.playlist ?? null;
  const choose = useMutation({
    mutationFn: ({ playlist }: { playlist: string | null; notice?: AddNotice }) => savePlaylistChoice(bookId, playlist),
    onSuccess: (view, { playlist, notice }) => {
      // Chọn xong phải thấy đã đổi (menu đóng ngay): nói tên danh sách vừa chọn (hay kết quả thêm nhạc, nếu việc chọn đến từ đó).
      if (notice) {
        toast[notice.kind](notice.title, { id: ADD_TOAST, description: [notice.description, "Đang dùng làm nhạc nền của cuốn này."].filter(Boolean).join("\n") });
      } else {
        const name = playlist === null ? "Tắt" : playlistOptions(menu.data).find((option) => option.id === playlist)?.label;
        if (name) toast(`Nhạc nền: ${name}`, { id: "playlist-choice", duration: 2500 });
      }
      client.setQueryData(key, view);
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] }); // số thay đổi của cuốn
      void client.invalidateQueries({ queryKey: ["listen", "library"] });
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error, { notice }) => {
      // Nhạc đã vào kho dù chưa chọn được: nói cả hai.
      toast.error("Chưa đổi được nhạc nền", { id: notice ? ADD_TOAST : undefined, description: [notice?.title, error.message].filter(Boolean).join("\n") });
    },
  });
  const addMusic = async () => {
    if (adding) return;
    adding = true;
    try {
      const { result, error } = await importMusic((done, total) => void toast.loading(`Đang thêm nhạc ${done}/${total}…`, { id: ADD_TOAST }));
      if (result) {
        client.setQueryData(MY_MUSIC_KEY, result);
        void client.invalidateQueries({ queryKey: ["music", "playlists"] }); // số bài của "Nhạc của tôi"
        void client.invalidateQueries({ queryKey: ["music-alternatives"] });
        const notice = addMusicOutcome(result);
        if (notice.select && chosen !== MINE_PLAYLIST) choose.mutate({ playlist: MINE_PLAYLIST, notice });
        else toast[notice.kind](notice.title, { id: ADD_TOAST, description: notice.description });
      } else {
        toast.dismiss(ADD_TOAST);
      }
      if (error) toast.error("Đang thêm nhạc thì dừng", { description: error.message });
    } catch (error) {
      toast.error("Không mở được hộp chọn file", { id: ADD_TOAST, description: (error as Error).message });
    } finally {
      adding = false;
    }
  };
  return {
    options: playlistOptions(menu.data, canImport),
    chosen,
    error: menu.data?.error ?? "",
    loading: menu.isLoading,
    choose: (id: string | null) => choose.mutate({ playlist: id }),
    canImport,
    addMusic,
  };
}

type AddNotice = ReturnType<typeof addMusicOutcome>;

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
  const { options, chosen, error, loading, choose, canImport, addMusic } = usePlaylistChoice(bookId);
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
          {canImport && (
            <DropdownMenu.Item onSelect={() => void addMusic()} className={cn(MENU_ITEM, "h-auto min-h-9 py-1.5")}>
              <Plus className="size-4 shrink-0" />
              {ADD_MUSIC_LABEL}
            </DropdownMenu.Item>
          )}
          {loading && <p className="px-2 py-1.5 text-xs text-fg-2">Đang tải các danh sách nhạc…</p>}
          <p className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{playlistNote(error)}</p>
        </DropdownMenu.SubContent>
      </DropdownMenu.Portal>
    </DropdownMenu.Sub>
  );
}
