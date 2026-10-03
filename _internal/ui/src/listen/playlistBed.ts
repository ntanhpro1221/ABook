// Nhạc nền cho sách nghe bằng "Nghe ngay" (docs/LISTEN_ANYTHING.md mục 4; máy chủ: webui/music_playlist.py; Android: Playlists.kt +
// MusicBed.kt). Sách chỉ có chữ không có không khí từng cảnh, nên người nghe chọn một DANH SÁCH PHÁT cho cả cuốn: một danh sách
// của danh mục, "Nhạc của tôi", hay tắt (mặc định). Lựa chọn nằm ở lớp sửa của sách (`music.playlist`), đi theo sách.
//
// Các bài nối nhau theo thứ tự trộn sẵn trên MỘT đồng hồ nhạc riêng của cuốn - đếm giây nghe thật, không theo giây của chương
// - nên sang chương mới nhạc chơi tiếp, không bắt đầu lại; chỗ đang tới nhớ trong máy theo cuốn + danh sách. Phần phát (mờ dần,
// chuyển bài, âm lượng theo `gainDb`) là chính MusicBed: mỗi bài là một "mốc" trên đồng hồ ấy.

import { api } from "@/studio/api";
import type { MusicBed, MusicCredit, MusicCue } from "./musicBed";

export const MINE_PLAYLIST = "mine";
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
  tracks: PlaylistTrack[];
  levelDb: number;
  credits?: Record<string, MusicCredit>;
  error?: string;
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
 *  sách, MINE_PLAYLIST, hay null = tắt. Trả màn "Nhạc nền" mới của cuốn. */
export function savePlaylistChoice<T = { playlist?: string }>(bookId: string, playlist: string | null): Promise<T> {
  return api<T>(`/api/books/${bookId}/music`, { method: "PUT", body: { playlist } });
}

export interface PlaylistOption {
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

/** Các lựa chọn của menu "Nhạc nền", theo thứ tự hiện: Tắt, các danh sách của danh mục, Nhạc của tôi. */
export function playlistOptions(menu: PlaylistMenu | undefined): PlaylistOption[] {
  return [
    { id: null, label: "Tắt", hint: "" },
    ...(menu?.playlists ?? []).map((item) => ({ id: item.id, label: item.name, hint: hours(item.minutes), description: item.description || undefined })),
    {
      id: MINE_PLAYLIST,
      label: "Nhạc của tôi",
      hint: menu?.mine ? `${menu.mine} bài` : "chưa có bài nào",
      // Đường thêm nhạc là nút “Nhập nhạc của tôi…” trong Sửa sách › Nhạc nền của sách nói (và tab Nhạc nền của Studio); sách chỉ có chữ chưa có.
      description: menu?.mine ? undefined : "Thêm nhạc của bạn ở “Sửa sách › Nhạc nền” của một cuốn sách nói (hay tab Nhạc nền trong Studio). Chưa thêm được ngay từ menu này.",
      disabled: !menu?.mine,
    },
  ];
}
