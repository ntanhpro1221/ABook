import { ActionSubmenu } from "@/shared/ActionMenu";
import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronRight, EighthNote, Plus } from "lucide-react";
import { toast } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { spokenProgress } from "@/shared/progressSpeech";
import { LiveText, ContentSkeleton, InlineError } from "@/shared/ui";
import { api } from "@/studio/api";
import { importMusic } from "@/studio/musicImport";
import { MY_MUSIC_KEY, useCanImportMusic } from "./MyMusic";
import { DEFAULT_LEVEL_DB } from "@/shared/musicLevels";
import { MUSIC_CHANGED_EVENT } from "./musicBed";
import {
  ADD_MUSIC_LABEL,
  addMusicOutcome,
  autoPlaylistName,
  chosenId,
  MINE_PLAYLIST,
  SCENE_PLAYLIST,
  playlistLabel,
  shortPlaylistLabel,
  playlistOptions,
  playlistPlaying,
  saveMusicLevel,
  savePlaylistChoice,
  type PlaylistMenu,
  type PlaylistOption,
  type PlaylistView,
} from "./playlistBed";

// "Nhạc nền" của sách chỉ có chữ (playlistBed.ts): chọn ở menu của sách và ở trình phát - cùng một lựa chọn, lưu vào phần sửa của
// sách nên đi theo sách. Máy tính hỏi máy chủ, điện thoại hỏi lõi native qua cùng đường (android/localStudio.ts).

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-lg px-2 text-sm outline-none data-[highlighted]:bg-hover";

const ADD_TOAST = "music-add";
/** Một lượt thêm nhạc tại một thời điểm: hộp chọn file đang mở / đang chép thì bấm nữa không mở thêm. Ở mức module vì menu đóng lại
 *  (hook gỡ ra) mà lượt thêm vẫn chạy tiếp. */
let adding = false;

/** Danh sách phát cho cuốn `bookId` (người nghe đã chọn, hay máy theo cảnh khi chưa chọn gì) + các lựa chọn + cách đổi. `chosen`: mã dòng được đánh dấu
 *  (null = "Để máy chọn"); `label`: chữ trên nút ("Máy chọn: <tên>" khi máy đang chọn); `playing`: có nhạc cho cuốn này. `enabled` false: chưa hỏi gì (menu chưa mở).
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
  const current = useQuery({ queryKey: key, queryFn: () => api<PlaylistView>(`/api/books/${bookId}/music`), enabled });
  const chosen = chosenId(current.data);
  const choose = useMutation({
    mutationFn: ({ playlist }: { playlist: string | null; notice?: AddNotice }) => savePlaylistChoice(bookId, playlist),
    onSuccess: (view, { playlist, notice }) => {
      // Chọn xong phải thấy đã đổi (menu đóng ngay): nói tên danh sách vừa chọn (hay kết quả thêm nhạc, nếu việc chọn đến từ đó).
      if (notice) {
        toast[notice.kind](notice.title, { id: ADD_TOAST, description: [notice.description, "Đang dùng làm nhạc nền của cuốn này."].filter(Boolean).join("\n") });
      } else {
        // Để máy chọn: lời đáp của server đã là màn của máy chọn - nói máy chọn gì.
        const auto = autoPlaylistName(view, menu.data);
        toast(playlist === null ? `Nhạc nền: để máy chọn${auto ? ` - ${auto}` : ""}` : `Nhạc nền: ${playlistLabel(view, menu.data)}`, {
          id: "playlist-choice",
          duration: 2500,
        });
      }
      client.setQueryData(key, view);
      // Chọn xong mà nhạc đang bị giữ vì mất mạng (điện thoại): lựa chọn đã lưu, bài tải khi có mạng - như Studio ("Đã lưu lựa chọn").
      if (view.error) toast.warning("Đã lưu lựa chọn", { id: "music-offline", description: view.error });
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] }); // số thay đổi của cuốn
      void client.invalidateQueries({ queryKey: ["listen", "library"] });
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error, { notice }) => {
      // Nhạc đã vào kho dù chưa chọn được: nói cả hai.
      toast.error("Chưa đổi được nhạc nền", { id: notice ? ADD_TOAST : undefined, description: [notice?.title, error.message].filter(Boolean).join("\n") });
    },
  });
  // Mức nhạc dưới giọng đọc: nhớ theo cuốn như danh sách; trình phát nạp lại hàng bài (MUSIC_CHANGED_EVENT) với mức mới.
  const setLevel = useMutation({
    mutationFn: (levelDb: number) => saveMusicLevel(bookId, levelDb),
    onSuccess: (view) => {
      client.setQueryData(key, view);
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error) => toast.error("Chưa chỉnh được mức nhạc", { description: error.message }),
  });
  const addMusic = async () => {
    if (adding) return;
    adding = true;
    try {
      // Trình đọc màn hình chỉ đọc mốc 25 %, không đọc lại sau mỗi bài (soát a31 A6).
      const { result, error } = await importMusic(
        (done, total) => void toast.loading(<LiveText shown={`Đang thêm nhạc ${done}/${total}…`} spoken={spokenProgress("Đang thêm nhạc", done / total)} />, { id: ADD_TOAST }),
      );
      if (result) {
        client.setQueryData(MY_MUSIC_KEY, result);
        void client.invalidateQueries({ queryKey: ["music", "playlists"] }); // số bài của "Nhạc của tôi"
        void client.invalidateQueries({ queryKey: ["music-alternatives"] });
        const notice = addMusicOutcome(result);
        // Chọn (lại) "Nhạc của tôi": sách mang theo đúng các bài đang có (book_edits.set_music), nên bài vừa thêm cũng vào sách dù cuốn đã đang dùng nó.
        if (notice.select) choose.mutate({ playlist: MINE_PLAYLIST, notice });
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
    options: playlistOptions(menu.data, canImport, current.data),
    chosen,
    label: playlistLabel(current.data, menu.data),
    playing: playlistPlaying(current.data),
    /** Nhạc của cuốn đang theo cảnh (người nghe chọn "Theo cảnh" hay để máy chọn). */
    scene: current.data?.playlist === SCENE_PLAYLIST,
    error: menu.data?.error || current.data?.error || "",
    loading: menu.isLoading,
    loadFailed: menu.isError || current.isError,
    retry: () => { void menu.refetch(); void current.refetch(); },
    choose: (id: string | null) => choose.mutate({ playlist: id }),
    /** Đang lưu lựa chọn; nút "Nhạc nền" của trình phát còn quay vòng chờ cả lúc máy xếp hàng bài ([usePlayer].musicLoading). */
    busy: choose.isPending,
    levelDb: current.data?.levelDb ?? DEFAULT_LEVEL_DB,
    setLevel: (levelDb: number) => setLevel.mutate(levelDb),
    levelBusy: setLevel.isPending,
    canImport,
    addMusic,
  };
}

type AddNotice = ReturnType<typeof addMusicOutcome>;

/** Một dòng lựa chọn: tên, độ dài (hay số bài), dấu đang chọn; mô tả danh sách ở dòng nhỏ dưới. */
export function PlaylistOptionLabel({ option, chosen }: { option: PlaylistOption; chosen: boolean }) {
  return (
    <>
      {/* Dấu chọn luôn chiếm chỗ, chỉ mờ vào / ra (menu còn mở khi chọn): không nhảy cứng. */}
      <Check aria-hidden className={cn("size-4 shrink-0 text-accent-text transition-opacity duration-motion-fast", chosen ? "opacity-100" : "opacity-0")} />
      <span className="min-w-0 flex-1">
        <span className="block text-pretty">{option.label}</span>
        {/* Mô tả luôn chừa chỗ hai dòng (đơn vị lh nên chữ hệ thống to thì chỗ chừa to theo; dòng thứ ba vẫn mở thêm, không cắt chữ): mô tả
            ngắn / dài xuống dòng khác nhau không làm các dòng của danh sách cao thấp khác nhau (59 / 48 dp - soát 25-10 V3). */}
        {option.description && <span className="block min-h-[2lh] text-pretty text-xs font-normal text-fg-3">{option.description}</span>}
      </span>
      {option.hint && <span className="shrink-0 text-xs font-normal text-fg-2">{option.hint}</span>}
    </>
  );
}

/** Chữ nhỏ dưới các lựa chọn: điều người nghe cần biết (mất mạng lần đầu thì lý do - chỉ nói khi đúng là đang xảy ra, không nhắc suông). `scene`: nhạc đang đổi
 *  theo cảnh, không chạy một mạch qua các chương. */
export function playlistNote(error: string, scene = false): string {
  if (error) return error;
  return scene ? "Nhạc nằm dưới giọng đọc và đổi theo từng cảnh của truyện." : "Nhạc nằm dưới giọng đọc và nghe tiếp qua các chương.";
}

/** Mục "Nhạc nền" trong menu của sách chỉ có chữ: menu con với các lựa chọn (điện thoại: một bước trong Sheet, xem ActionMenu.tsx). */
export function PlaylistSubmenu({ bookId }: { bookId: string }) {
  const { options, chosen, label, scene, error, loading, loadFailed, retry, choose, canImport, addMusic } = usePlaylistChoice(bookId);
  return (
    <ActionSubmenu
      id="music"
      label="Nhạc nền"
      itemClassName={MENU_ITEM}
      trigger={<>
        <EighthNote className="size-4" />
        <span className="flex-1">Nhạc nền</span>
        <span className="max-w-44 truncate text-xs text-fg-2" title={label}>{shortPlaylistLabel(label)}</span>
        <ChevronRight className="ink-end size-4 text-fg-2" />
      </>}
    >
      {/* Hàng thật về sau khung chờ / đổi danh sách: mờ qua cả nhóm, cao đổi dần. */}
      <MotionRegion motionKey={options.map((option) => JSON.stringify(option.id))}>
      {options.map((option) => (
        <DropdownMenu.Item
          key={JSON.stringify(option.id)}
          disabled={option.disabled}
          onSelect={() => choose(option.id)}
          className={cn(MENU_ITEM, "h-auto min-h-9 py-1.5 transition-colors duration-motion-fast data-[disabled]:opacity-50", option.id === chosen && "font-semibold")}
        >
          <PlaylistOptionLabel option={option} chosen={option.id === chosen} />
        </DropdownMenu.Item>
      ))}
      </MotionRegion>
      {canImport && (
        <DropdownMenu.Item onSelect={() => void addMusic()} className={cn(MENU_ITEM, "h-auto min-h-9 py-1.5")}>
          <Plus className="size-4 shrink-0" />
          {ADD_MUSIC_LABEL}
        </DropdownMenu.Item>
      )}
      <MotionRegion motionKey={[loading, loadFailed]}>{loading ? <ContentSkeleton count={2} label="Đang tải danh sách" className="p-2" /> : loadFailed ? <InlineError message="Bạn hãy thử tải lại danh sách nhạc." onRetry={retry} /> : null}</MotionRegion>
      <MotionRegion as="p" className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{playlistNote(error, scene)}</MotionRegion>
    </ActionSubmenu>
  );
}
