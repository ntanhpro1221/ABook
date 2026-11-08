import { S } from "../shared/strings.generated";
import { ActionSubmenu } from "@/shared/ActionMenu";
import { MotionRegion } from "@/shared/MotionRegion";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, EighthNote, Plus } from "lucide-react";
import { toast } from "@/shared/toast";
import { cn } from "@/shared/cn";
import { spokenProgress } from "@/shared/progressSpeech";
import { LiveText, ContentSkeleton, InlineError, SelectionMark } from "@/shared/ui";
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

const MENU_ITEM = "flex h-9 cursor-default items-center gap-2 rounded-control px-2 text-sm outline-none data-[highlighted]:bg-hover";

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
    scope: { id: `book-music:${bookId}` },
    mutationFn: ({ playlist }: { playlist: string | null; notice?: AddNotice }) => savePlaylistChoice(bookId, playlist),
    onSuccess: (view, { playlist, notice }) => {
      // Chọn xong phải thấy đã đổi (menu đóng ngay): nói tên danh sách vừa chọn (hay kết quả thêm nhạc, nếu việc chọn đến từ đó).
      if (notice) {
        toast[notice.kind](notice.title, { id: ADD_TOAST, description: [notice.description, S.s_dang_dung_lam_nhac_nen_cua_cuon_nay_9cab7be5].filter(Boolean).join("\n") });
      } else {
        // Để máy chọn: lời đáp của server đã là màn của máy chọn - nói máy chọn gì.
        const auto = autoPlaylistName(view, menu.data);
        toast(playlist === null ? S.s_nhac_nen_de_may_chon_0_76676aa5(auto ? ` - ${auto}` : "") : S.s_nhac_nen_0_2890a0c1(playlistLabel(view, menu.data)), {
          id: "playlist-choice",
          duration: 2500,
        });
      }
      client.setQueryData(key, view);
      // Chọn xong mà nhạc đang bị giữ vì mất mạng (điện thoại): lựa chọn đã lưu, bài tải khi có mạng - như Studio ("Đã lưu lựa chọn").
      if (view.error) toast.warning(S.s_da_luu_lua_chon_3dbba0c5, { id: "music-offline", description: view.error });
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] }); // số thay đổi của cuốn
      void client.invalidateQueries({ queryKey: ["listen", "library"] });
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error, { notice }) => {
      // Nhạc đã vào kho dù chưa chọn được: nói cả hai.
      toast.error(S.s_chua_doi_duoc_nhac_nen_b5d19c42, { id: notice ? ADD_TOAST : undefined, description: [notice?.title, error.message].filter(Boolean).join("\n") });
    },
  });
  // Mức nhạc nền: nhớ theo cuốn như danh sách; trình phát nạp lại hàng bài (MUSIC_CHANGED_EVENT) với mức mới.
  const setLevel = useMutation({
    scope: { id: `book-music:${bookId}` },
    mutationFn: (levelDb: number) => saveMusicLevel(bookId, levelDb),
    onSuccess: (view) => {
      client.setQueryData(key, view);
      void client.invalidateQueries({ queryKey: ["listen", "book", bookId] });
      window.dispatchEvent(new CustomEvent(MUSIC_CHANGED_EVENT, { detail: bookId }));
    },
    onError: (error: Error) => toast.error(S.s_chua_chinh_duoc_muc_nhac_4ed5127b, { description: error.message }),
  });
  const addMusic = async () => {
    if (adding) return;
    adding = true;
    try {
      // Trình đọc màn hình chỉ đọc mốc 25 %, không đọc lại sau mỗi bài (soát a31 A6).
      const { result, error } = await importMusic(
        (done, total) => void toast.loading(<LiveText shown={S.s_dang_them_nhac_0_1_a3b58965(done, total)} spoken={spokenProgress(S.s_dang_them_nhac_b14bb1bb, done / total)} />, { id: ADD_TOAST }),
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
      if (error) toast.error(S.s_dang_them_nhac_thi_dung_8712c030, { description: error.message });
    } catch (error) {
      toast.error(S.s_chua_mo_duoc_hop_chon_file_17d8e8aa, { id: ADD_TOAST, description: (error as Error).message });
    } finally {
      adding = false;
    }
  };
  return {
    options: playlistOptions(menu.data, canImport, current.data),
    chosen,
    label: playlistLabel(current.data, menu.data),
    playing: playlistPlaying(current.data),
    /** Đã biết nhạc của cuốn (chưa tải xong thì chưa nói "Tắt" - soát điện thoại 26-10: hiện "Tắt" 300 ms rồi đổi thành "Theo cảnh"). */
    known: current.data !== undefined,
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
      <SelectionMark selected={chosen} />
      <span className="min-w-0 flex-1">
        <span className="block text-pretty">{option.label}</span>
        {/* Mô tả luôn chừa chỗ hai dòng (đơn vị lh nên chữ hệ thống to thì chỗ chừa to theo; dòng thứ ba vẫn mở thêm, không cắt chữ): mô tả
            ngắn / dài xuống dòng khác nhau không làm các dòng của danh sách cao thấp khác nhau (59 / 48 dp - soát 25-10 V3). */}
        {option.description && <span className="block min-h-[2lh] text-pretty text-xs font-normal text-fg-3">{option.description}</span>}
      </span>
      {/* Gợi ý là chữ phụ: nhường chỗ (xuống dòng) cho tên lựa chọn - "Nhạc của tôi" từng gãy thành hai dòng cạnh "chưa có bài nào" (luật
          label-wrapped-beside-note). */}
      {option.hint && <span className="min-w-0 max-w-[45%] text-right text-pretty text-xs font-normal text-fg-2">{option.hint}</span>}
    </>
  );
}


/** Mục "Nhạc nền" trong menu của sách chỉ có chữ: menu con với các lựa chọn (điện thoại: một bước trong Sheet, xem ActionMenu.tsx). */
export function PlaylistSubmenu({ bookId }: { bookId: string }) {
  const { options, chosen, label, error, loading, loadFailed, retry, choose, canImport, addMusic } = usePlaylistChoice(bookId);
  return (
    <ActionSubmenu
      id="music"
      label={S.s_nhac_nen_271fb292}
      itemClassName={MENU_ITEM}
      trigger={<>
        <EighthNote className="size-4" />
        <span className="flex-1">{S.s_nhac_nen_271fb292}</span>
        <span className="max-w-[45%] text-right text-xs text-fg-2 [overflow-wrap:anywhere]">{shortPlaylistLabel(label)}</span>
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
      <MotionRegion motionKey={[loading, loadFailed]}>{loading ? <ContentSkeleton count={2} label={S.s_dang_tai_danh_sach_831ab748} className="p-2" /> : loadFailed ? <InlineError message={S.s_ban_hay_thu_tai_lai_danh_sach_nhac_c3976285} onRetry={retry} /> : null}</MotionRegion>
      {/* Chữ nhỏ chỉ khi có điều cần biết (mất mạng lần đầu thì lý do) - như bản điện thoại, không nhắc suông. */}
      <MotionRegion motionKey={error}>{error ? <p data-menu-note className="px-2 pb-1 pt-1.5 text-xs text-fg-2">{error}</p> : null}</MotionRegion>
    </ActionSubmenu>
  );
}
