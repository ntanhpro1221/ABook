// Nhạc nền cho sách nghe bằng "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 4; máy chủ: webui/music_playlist.py; Android: Playlists.kt +
// MusicBed.kt). Sách chỉ có chữ không có không khí từng cảnh, nên người nghe chọn một DANH SÁCH PHÁT cho cả cuốn: một danh sách
// của danh mục, "Nhạc của tôi", tắt ("off"), hay - khi chưa chọn gì (mặc định) - để MÁY CHỌN danh sách hợp với cuốn (webui/music_playlist.py
// `pick`, Playlists.pick). Lựa chọn nằm ở lớp sửa của sách (`music.playlist`), đi theo sách; không có khoá = máy chọn.
//
// Các bài nối nhau theo thứ tự trộn sẵn trên MỘT đồng hồ nhạc riêng của cuốn - đếm giây nghe thật, không theo giây của chương
// - nên sang chương mới nhạc chơi tiếp, không bắt đầu lại; chỗ đang tới nhớ trong máy theo cuốn + danh sách. Phần phát (mờ dần,
// chuyển bài, âm lượng theo `gainDb`) là chính MusicBed: mỗi bài là một "mốc" trên đồng hồ ấy.

import { api } from "@/studio/api";
import type { ImportResult } from "@/studio/musicLocal";
import type { MusicBed, MusicCredit, MusicCue } from "./musicBed";

export const MINE_PLAYLIST = "mine";
/** `music.playlist` = "off": người nghe tắt nhạc nền (khác với không có khoá = để máy chọn). */
export const OFF_PLAYLIST = "off";
/** Bài không biết độ dài: khoảng mặc định trên đồng hồ (bài ngắn hơn thì lặp liền như mọi bài nhạc nền). */
export const FALLBACK_SECONDS = 180;
/** Bằng thời gian chuyển mờ của MusicBed: bài sau vào lúc bài trước bắt đầu mờ, bài trước tắt hẳn đúng lúc nó hết. */
export const OVERLAP_SECONDS = 2;
/** Giọng ngừng giây lát giữa hai đoạn / hai chương thì nhạc không ngắt. */
export const PAUSE_GRACE_MS = 2500;
/** Đồng hồ không nhảy xa khi máy ngủ giữa hai nhịp. */
const MAX_STEP_SECONDS = 3;
const SAVE_EVERY_MS = 5000;

export interface PlaylistTrack {
  link: string;
  src: string;
  /** Giây; null = danh mục không nói. */
  duration: number | null;
  gainDb?: number;
}

/** GET /api/books/<mã>/music/playlist: hàng bài theo thứ tự phát (rỗng = tắt, hay sách có nhạc của người làm sách). */
export interface PlaylistQueue {
  playlist: string | null;
  /** true khi `playlist` do máy chọn (người nghe chưa chọn gì). */
  playlistAuto?: boolean;
  tracks: PlaylistTrack[];
  levelDb: number;
  credits?: Record<string, MusicCredit>;
  error?: string;
}

/** Phần của màn "Nhạc nền" của cuốn (GET /api/books/<mã>/music) nói về danh sách phát: mã người nghe đã chọn ("mine", "off", mã danh sách), hay -
 *  khi chưa chọn gì và máy chọn được - mã máy chọn kèm `playlistAuto` true. */
export interface PlaylistView {
  playlist?: string;
  playlistAuto?: boolean;
  /** Cuốn chưa chọn nhạc và người dùng đã tắt "tự chọn nhạc nền" trong Cài đặt: chưa có nhạc cho cuốn này. */
  autoOff?: boolean;
  /** Mức nhạc dưới giọng đọc (dB) người nghe đã chọn cho cuốn, hay mặc định của máy khi chưa chọn. */
  levelDb?: number;
}

export interface PlaylistSummary {
  id: string;
  name: string;
  description: string;
  minutes: number;
  count: number;
}

/** GET /api/music/playlists: menu chọn nhạc nền. */
export interface PlaylistMenu {
  playlists: PlaylistSummary[];
  /** Số bài trong "Nhạc của tôi" của máy này. */
  mine: number;
  error: string;
}

/** Mỗi bài một mốc trên đồng hồ nhạc: dài (độ dài - OVERLAP_SECONDS), ít nhất 1 giây. Khoá theo thứ tự, nên một bài có mặt hai lần
 *  vẫn là hai mốc. */
export function playlistCues(tracks: PlaylistTrack[]): MusicCue[] {
  let at = 0;
  return tracks.map((track, index) => {
    const length = Math.max(1, (track.duration && track.duration > 0 ? track.duration : FALLBACK_SECONDS) - OVERLAP_SECONDS);
    const cue: MusicCue = { start: at, end: at + length, link: track.link, key: `${index}:${track.link}`, src: track.src, gainDb: track.gainDb };
    at += length;
    return cue;
  });
}

/** Giây `seconds` của đồng hồ nhạc, quay vòng: hết danh sách thì lại bài đầu. */
export function wrapSeconds(seconds: number, cues: MusicCue[]): number {
  const total = cues.length ? cues[cues.length - 1].end : 0;
  return total > 0 ? ((seconds % total) + total) % total : 0;
}

type Store = Pick<Storage, "getItem" | "setItem">;

function browserStorage(): Store | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** Đồng hồ nhạc của một cuốn + danh sách: số giây nhạc đã chơi, nhớ trong máy (không có chỗ nhớ thì bắt đầu từ bài đầu). */
export class PlaylistClock {
  seconds = 0;
  private at: number | null = null;

  constructor(
    private readonly key: string,
    private readonly storage: Store | null = browserStorage(),
    private readonly now: () => number = () => Date.now(),
  ) {
    try {
      const saved = Number(this.storage?.getItem(this.storageKey));
      if (Number.isFinite(saved) && saved > 0) this.seconds = saved;
    } catch {
      // không đọc được chỗ nhớ: bắt đầu từ đầu
    }
  }

  private get storageKey(): string {
    return `abook:playlist-clock:${this.key}`;
  }

  /** Cộng thời gian đã chơi từ lần trước (nếu đang chạy) và chạy / đứng từ giờ theo `running`. */
  tick(running: boolean): void {
    const now = this.now();
    if (this.at !== null) this.seconds += Math.min(Math.max(0, (now - this.at) / 1000), MAX_STEP_SECONDS);
    this.at = running ? now : null;
  }

  save(): void {
    try {
      this.storage?.setItem(this.storageKey, String(Math.round(this.seconds * 10) / 10));
    } catch {
      // đầy / bị chặn: lần sau bắt đầu lại từ chỗ đã nhớ trước đó
    }
  }
}

type Timers = { setTimeout: (run: () => void, ms: number) => unknown; clearTimeout: (handle: unknown) => void };
const realTimers: Timers = {
  setTimeout: (run, ms) => globalThis.setTimeout(run, ms),
  clearTimeout: (handle) => globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>),
};

/** Lái MusicBed theo đồng hồ nhạc thay cho giây của chương: `update(giọng đang chạy?)` mỗi khi bộ máy phát báo thời gian / phát /
 *  dừng. Giọng dừng quá PAUSE_GRACE_MS thì nhạc dừng theo; dừng ngắn hơn (nối hai đoạn, sang chương) thì nhạc không ngắt. */
export class PlaylistDriver {
  private playing = false;
  private grace: unknown = null;
  private savedAt = 0;

  constructor(
    private readonly bed: Pick<MusicBed, "sync">,
    private readonly clock: PlaylistClock,
    private readonly cues: MusicCue[],
    private readonly timers: Timers = realTimers,
    private readonly now: () => number = () => Date.now(),
  ) {}

  update(voicePlaying: boolean): void {
    if (voicePlaying) {
      this.clearGrace();
      this.playing = true;
      this.clock.tick(true);
    } else if (this.playing && this.grace === null) {
      this.grace = this.timers.setTimeout(() => {
        this.grace = null;
        this.playing = false;
        this.clock.tick(false);
        this.push();
        this.clock.save();
      }, PAUSE_GRACE_MS);
    }
    this.push();
    if (this.now() - this.savedAt > SAVE_EVERY_MS) {
      this.savedAt = this.now();
      this.clock.save();
    }
  }

  /** Thôi lái (đổi cuốn, đổi danh sách, đóng trình phát): ghi chỗ đang tới. */
  stop(): void {
    this.clearGrace();
    this.clock.tick(false);
    this.clock.save();
  }

  private push(): void {
    this.bed.sync(wrapSeconds(this.clock.seconds, this.cues), this.playing);
  }

  private clearGrace(): void {
    if (this.grace === null) return;
    this.timers.clearTimeout(this.grace);
    this.grace = null;
  }
}

/** Lưu lựa chọn nhạc nền của một cuốn vào lớp sửa của nó (máy tính: máy chủ; điện thoại: lõi native qua cùng đường): mã danh
 *  sách, MINE_PLAYLIST, OFF_PLAYLIST = tắt, hay null = xoá lựa chọn để máy tự chọn. Trả màn "Nhạc nền" mới của cuốn. */
export function savePlaylistChoice<T = PlaylistView>(bookId: string, playlist: string | null): Promise<T> {
  return api<T>(`/api/books/${bookId}/music`, { method: "PUT", body: { playlist } });
}

/** Lưu mức nhạc dưới giọng đọc của một cuốn (cùng lệnh PUT như chọn danh sách; máy chủ và lõi native áp mức này khi dựng hàng bài). */
export function saveMusicLevel(bookId: string, levelDb: number): Promise<PlaylistView> {
  return api<PlaylistView>(`/api/books/${bookId}/music`, { method: "PUT", body: { levelDb } });
}

export interface PlaylistOption {
  /** null = "Để máy chọn" (gửi `playlist: null`, server xoá khoá); OFF_PLAYLIST = "Tắt". */
  id: string | null;
  label: string;
  hint: string;
  description?: string;
  disabled?: boolean;
}

function hours(minutes: number): string {
  // Là độ dài cả danh sách phát, không phải giờ nào trong ngày: nói "dài" để "8 giờ" không đọc như 8 giờ sáng.
  if (minutes <= 0) return "";
  if (minutes < 90) return `dài ${minutes} phút`;
  return `dài ${Math.round(minutes / 60)} giờ`;
}

/** Mục thêm nhạc ở cuối menu "Nhạc nền" (chỉ khi máy nhập được nhạc). */
export const ADD_MUSIC_LABEL = "Thêm nhạc của bạn…";

/** Lời nói khi "Nhạc của tôi" còn trống. Máy nhập được thì mục "Thêm nhạc của bạn…" ngay dưới đã là đường đi (không cần nói thêm);
 *  máy không nhập được (điện thoại nghe thư viện máy tính, Studio từ xa) thì chỉ đường sang máy tính. */
export function emptyMineHint(canImport: boolean): string | undefined {
  return canImport ? undefined : "Máy này chưa thêm nhạc được. Thêm ở ABook trên máy tính (tab Nhạc nền của Studio), bài sẽ có ở đây.";
}

/** Câu báo sau khi thêm nhạc từ menu: bao nhiêu bài vào, và có nên chọn "Nhạc của tôi" cho cuốn đang nghe không (có bài trong kho là chọn;
 *  không vào được bài nào thì không đổi gì). Phần đã nhập vẫn giữ khi có file lỗi. */
export function addMusicOutcome(result: Pick<ImportResult, "added" | "existing" | "failed">): {
  select: boolean;
  kind: "success" | "warning" | "error";
  title: string;
  description?: string;
} {
  const { added, existing, failed } = result;
  const description = failed.join("\n") || undefined;
  if (added.length) return { select: true, kind: failed.length ? "warning" : "success", title: `Đã thêm ${added.length} bài`, description };
  if (existing.length) return { select: true, kind: failed.length ? "warning" : "success", title: "Những bài này đã có trong Nhạc của tôi", description };
  return { select: false, kind: "error", title: failed.length > 1 ? "Không thêm được file nào" : "Không thêm được file này", description };
}

export const AUTO_LABEL = "Để máy chọn";
export const OFF_LABEL = "Tắt";

/** Mã option đang được đánh dấu: null = "Để máy chọn" (chưa chọn gì, kể cả khi máy chưa chọn được gì), còn lại là mã người nghe đã chọn. */
export function chosenId(view: PlaylistView | undefined): string | null {
  return view?.playlistAuto ? null : view?.playlist ?? null;
}

/** Tên danh sách `code` trong menu; menu chưa tải thì "" (không nói mã trần cho người nghe). */
function nameOf(menu: PlaylistMenu | undefined, code: string): string {
  return menu?.playlists.find((item) => item.id === code)?.name ?? "";
}

/** Tên danh sách máy đang chọn cho cuốn; "" khi người nghe đã chọn (hay máy chưa chọn được gì, hay menu chưa tải). */
export function autoPlaylistName(view: PlaylistView | undefined, menu: PlaylistMenu | undefined): string {
  return view?.playlistAuto ? nameOf(menu, view.playlist ?? "") : "";
}

/** Chữ trên nút / thông báo của lựa chọn hiện tại: "Máy chọn: <tên>" khi máy đang chọn, "Tắt", tên danh sách, hay "Nhạc của tôi". */
export function playlistLabel(view: PlaylistView | undefined, menu: PlaylistMenu | undefined): string {
  if (view?.playlistAuto) return ["Máy chọn", autoPlaylistName(view, menu)].filter(Boolean).join(": ");
  if (!view?.playlist) return view?.autoOff ? "Chưa có nhạc (tắt trong Cài đặt)" : "Máy chọn";
  if (view.playlist === OFF_PLAYLIST) return OFF_LABEL;
  if (view.playlist === MINE_PLAYLIST) return "Nhạc của tôi";
  // Danh mục chưa tải (mất mạng lần đầu): không nói mã trần ("fantasy_adventure") cho người nghe.
  return nameOf(menu, view.playlist) || "Danh sách đã chọn";
}

/** Công tắc "Tự chọn nhạc nền" ở Cài đặt > Nhạc nền (máy tính và điện thoại dùng chung lời). */
export const AUTO_MUSIC_LABEL = "Tự chọn nhạc nền cho sách chỉ có chữ";
export const AUTO_MUSIC_HINT =
  "Máy chọn một bộ nhạc hợp với truyện (kỳ ảo, học đường, kiếm hiệp…) rồi phát nhè nhẹ dưới giọng đọc. Tắt thì sách chưa chọn nhạc sẽ im lặng; cuốn nào bạn đã chọn nhạc ở menu “Nhạc nền” của sách vẫn có nhạc.";

/** Nhạc đang chạy cho cuốn này hay không (máy chọn được, hay người nghe chọn một danh sách) - để nút "Nhạc nền" sáng lên. */
export function playlistPlaying(view: PlaylistView | undefined): boolean {
  return Boolean(view?.playlist) && view?.playlist !== OFF_PLAYLIST;
}

/** Các lựa chọn của menu "Nhạc nền", theo thứ tự hiện: Để máy chọn, Tắt, các danh sách của danh mục, Nhạc của tôi. `canImport`: máy nhập được
 *  nhạc. `view`: lựa chọn hiện tại - khi máy đang chọn, dòng "Để máy chọn" nói máy chọn danh sách nào. */
export function playlistOptions(menu: PlaylistMenu | undefined, canImport = false, view?: PlaylistView): PlaylistOption[] {
  return [
    { id: null, label: AUTO_LABEL, hint: view?.autoOff ? "đang tắt trong Cài đặt" : autoPlaylistName(view, menu) },
    { id: OFF_PLAYLIST, label: OFF_LABEL, hint: "" },
    ...(menu?.playlists ?? []).map((item) => ({ id: item.id, label: item.name, hint: hours(item.minutes), description: item.description || undefined })),
    {
      id: MINE_PLAYLIST,
      label: "Nhạc của tôi",
      hint: menu?.mine ? `${menu.mine} bài` : "chưa có bài nào",
      description: menu?.mine ? undefined : emptyMineHint(canImport),
      disabled: !menu?.mine,
    },
  ];
}
