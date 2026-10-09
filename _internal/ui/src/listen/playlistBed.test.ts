import { afterEach, describe, expect, it } from "vitest";
import { setApiTransport } from "@/studio/api";
import type { MusicCue } from "./musicBed";
import {
  addMusicOutcome,
  autoPlaylistName,
  chosenId,
  FALLBACK_SECONDS,
  MINE_PLAYLIST,
  OFF_PLAYLIST,
  OVERLAP_SECONDS,
  PAUSE_GRACE_MS,
  PlaylistClock,
  PlaylistDriver,
  playlistCues,
  playlistLabel,
  playlistOptions,
  playlistPlaying,
  savePlaylistChoice,
  wrapSeconds,
  type PlaylistTrack,
} from "./playlistBed";

const tracks: PlaylistTrack[] = [
  { link: "https://x/b.mp3", src: "/b", duration: 200, gainDb: -22 },
  { link: "https://x/a.mp3", src: "/a", duration: null },
  { link: "https://x/b.mp3", src: "/b", duration: 60 },
];

function memory(): Pick<Storage, "getItem" | "setItem"> & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return { data, getItem: (key) => data.get(key) ?? null, setItem: (key, value) => void data.set(key, value) };
}

/** Bộ hẹn giờ tay: chạy hàm hẹn khi kim đi qua mốc. */
function fakeTimers() {
  let now = 0;
  const pending: { at: number; run: () => void; id: number }[] = [];
  let next = 1;
  return {
    now: () => now,
    timers: {
      setTimeout: (run: () => void, ms: number) => {
        pending.push({ at: now + ms, run, id: next });
        return next++;
      },
      clearTimeout: (id: unknown) => {
        const index = pending.findIndex((item) => item.id === id);
        if (index >= 0) pending.splice(index, 1);
      },
    },
    advance(ms: number) {
      now += ms;
      for (const item of [...pending].sort((a, b) => a.at - b.at)) {
        if (item.at > now) continue;
        pending.splice(pending.indexOf(item), 1);
        item.run();
      }
    },
  };
}

/** MusicBed giả: ghi lại giây đồng hồ nhạc và trạng thái phát của mỗi lần đồng bộ. */
function fakeBed(cues: MusicCue[]) {
  const calls: { seconds: number; playing: boolean; key: string | null }[] = [];
  return {
    calls,
    sync(seconds: number, playing: boolean) {
      calls.push({ seconds, playing, key: cues.find((cue) => seconds >= cue.start && seconds < cue.end)?.key ?? null });
    },
    get last() {
      return calls[calls.length - 1];
    },
  };
}

describe("danh sách phát trên đồng hồ nhạc của cuốn", () => {
  it("các bài nối nhau theo thứ tự trộn sẵn, bài sau vào khi bài trước bắt đầu mờ", () => {
    const cues = playlistCues(tracks);
    expect(cues.map((cue) => [cue.start, cue.end])).toEqual([
      [0, 200 - OVERLAP_SECONDS],
      [198, 198 + FALLBACK_SECONDS - OVERLAP_SECONDS],
      [376, 376 + 60 - OVERLAP_SECONDS],
    ]);
    expect(cues.map((cue) => cue.link)).toEqual(tracks.map((track) => track.link));
    expect(new Set(cues.map((cue) => cue.key)).size).toBe(3); // một bài có mặt hai lần vẫn là hai mốc
    expect(cues[0].gainDb).toBe(-22);
    expect(wrapSeconds(434 + 5, cues)).toBe(5); // hết danh sách thì lại bài đầu
    expect(wrapSeconds(5, [])).toBe(0);
  });

  it("nhạc chạy tiếp qua chỗ giọng ngừng ngắn (sang chương) và không bắt đầu lại", () => {
    const cues = playlistCues(tracks);
    const time = fakeTimers();
    const storage = memory();
    const bed = fakeBed(cues);
    const driver = new PlaylistDriver(bed, new PlaylistClock("sach:calm", storage, time.now), cues, time.timers, time.now);
    driver.update(true);
    for (let second = 0; second < 205; second += 1) {
      time.advance(1000);
      driver.update(true);
    }
    expect(bed.last.key).toBe(cues[1].key);
    const before = bed.last.seconds;
    // Hết chương 1: giọng ngừng chừng một giây rồi đọc chương 2 - nhạc không dừng, đồng hồ không về 0.
    driver.update(false);
    time.advance(1000);
    expect(bed.last.playing).toBe(true);
    driver.update(true);
    time.advance(1000);
    driver.update(true);
    expect(bed.last.playing).toBe(true);
    expect(bed.last.seconds).toBeGreaterThan(before);
    expect(bed.last.key).toBe(cues[1].key);
  });

  it("giọng dừng hẳn thì nhạc dừng theo, đồng hồ đứng; mở lại cuốn là nghe tiếp đúng chỗ", () => {
    const cues = playlistCues(tracks);
    const time = fakeTimers();
    const storage = memory();
    const bed = fakeBed(cues);
    const driver = new PlaylistDriver(bed, new PlaylistClock("sach:calm", storage, time.now), cues, time.timers, time.now);
    driver.update(true);
    for (let second = 0; second < 30; second += 1) {
      time.advance(1000);
      driver.update(true);
    }
    driver.update(false);
    time.advance(PAUSE_GRACE_MS + 1);
    expect(bed.last.playing).toBe(false);
    const stopped = bed.last.seconds;
    time.advance(60_000); // dừng một phút: đồng hồ nhạc không chạy
    driver.update(false);
    expect(bed.last.seconds).toBe(stopped);
    driver.stop();
    // Mở lại (trình phát mới, cùng máy): đồng hồ đọc lại chỗ đã nhớ.
    const again = new PlaylistClock("sach:calm", storage, time.now);
    expect(again.seconds).toBeCloseTo(stopped, 0);
    expect(new PlaylistClock("sach:khac", storage, time.now).seconds).toBe(0); // danh sách khác: đồng hồ riêng
  });

  it("đồng hồ không nhảy xa khi máy ngủ giữa hai nhịp, và chạy được khi không có chỗ nhớ", () => {
    let now = 0;
    const clock = new PlaylistClock("x", null, () => now);
    clock.tick(true);
    now = 10 * 60_000;
    clock.tick(true);
    expect(clock.seconds).toBe(3);
    clock.save(); // không có chỗ nhớ: không lỗi
  });
});

describe("lựa chọn nhạc nền", () => {
  afterEach(() => setApiTransport(null));

  it("menu: Để máy chọn, Tắt, các danh sách của danh mục, rồi Nhạc của tôi (tắt được khi chưa có bài)", () => {
    const options = playlistOptions({
      playlists: [
        { id: "calm", name: "Kỳ ảo êm đềm", description: "Cho truyện chậm.", minutes: 545, count: 84 },
        { id: "short", name: "Ngắn", description: "", minutes: 40, count: 9 },
      ],
      mine: 0,
      error: "",
    });
    expect(options.map((option) => option.id)).toEqual([null, OFF_PLAYLIST, "calm", "short", MINE_PLAYLIST]);
    expect(options[0]).toMatchObject({ label: "Để máy chọn", hint: "" });
    expect(options[1]).toMatchObject({ label: "Tắt" });
    expect(options[2]).toMatchObject({ label: "Kỳ ảo êm đềm", hint: "dài 9 giờ", description: "Cho truyện chậm." });
    expect(options[3].hint).toBe("dài 40 phút");
    expect(options[4]).toMatchObject({ label: "Nhạc của tôi", disabled: true });
    // Máy không nhập được nhạc: chỉ đường sang máy tính; máy nhập được: mục "Thêm nhạc của bạn…" ngay dưới đã là đường đi.
    expect(options[4].description).toContain("trên máy tính");
    expect(options[4].description).not.toContain("Sửa sách");
    expect(playlistOptions({ playlists: [], mine: 0, error: "" }, true)[2].description).toBeUndefined();
    expect(playlistOptions({ playlists: [], mine: 3, error: "" })[2]).toMatchObject({ id: MINE_PLAYLIST, hint: "3 bài", disabled: false });
    expect(playlistOptions(undefined).map((option) => option.id)).toEqual([null, OFF_PLAYLIST, MINE_PLAYLIST]);
  });

  const menu = { playlists: [{ id: "calm", name: "Kỳ ảo êm đềm", description: "", minutes: 60, count: 9 }], mine: 0, error: "" };

  it("đang để máy chọn: nút nói 'Máy chọn: <tên>', dòng 'Để máy chọn' được đánh dấu và nói máy chọn gì", () => {
    const view = { playlist: "calm", playlistAuto: true };
    expect(chosenId(view)).toBeNull();
    expect(playlistLabel(view, menu)).toBe("Máy chọn: Kỳ ảo êm đềm");
    expect(autoPlaylistName(view, menu)).toBe("Kỳ ảo êm đềm");
    expect(playlistOptions(menu, false, view)[0]).toMatchObject({ id: null, hint: "Kỳ ảo êm đềm" });
    expect(playlistPlaying(view)).toBe(true);
    // menu chưa tải: không nói mã trần cho người nghe
    expect(playlistLabel(view, undefined)).toBe("Máy chọn");
  });

  it("đã chọn: danh sách cụ thể, Nhạc của tôi, hay Tắt (không còn máy chọn)", () => {
    expect(chosenId({ playlist: "calm" })).toBe("calm");
    expect(playlistLabel({ playlist: "calm" }, menu)).toBe("Kỳ ảo êm đềm");
    expect(playlistLabel({ playlist: MINE_PLAYLIST }, menu)).toBe("Nhạc của tôi");
    expect(chosenId({ playlist: OFF_PLAYLIST })).toBe(OFF_PLAYLIST);
    expect(playlistLabel({ playlist: OFF_PLAYLIST }, menu)).toBe("Tắt");
    expect(playlistPlaying({ playlist: OFF_PLAYLIST })).toBe(false);
    expect(autoPlaylistName({ playlist: "calm" }, menu)).toBe("");
    // chưa chọn gì mà máy cũng chưa chọn được: vẫn là "Để máy chọn", không có nhạc
    expect(chosenId({})).toBeNull();
    expect(playlistPlaying({})).toBe(false);
    expect(playlistPlaying(undefined)).toBe(false);
  });

  it("thêm nhạc từ menu: có bài vào thì chọn Nhạc của tôi, không bài nào vào thì không đổi gì", () => {
    const track = { link: "local:x", title: "A", creator: "", analysed: false } as never;
    expect(addMusicOutcome({ added: [track, track], existing: [], failed: [] })).toEqual({ select: true, kind: "success", title: "Đã thêm 2 bài", description: undefined });
    expect(addMusicOutcome({ added: [track], existing: [], failed: ["b.mp3: hỏng"] })).toMatchObject({ select: true, kind: "warning", description: "b.mp3: hỏng" });
    expect(addMusicOutcome({ added: [], existing: [track], failed: [] })).toMatchObject({ select: true, kind: "success", title: "Những bài này đã có trong Nhạc của tôi" });
    expect(addMusicOutcome({ added: [], existing: [], failed: ["b.mp3: hỏng"] })).toMatchObject({ select: false, kind: "error", title: "Không thêm được file này" });
  });

  it("lưu vào phần sửa của cuốn qua cùng đường trên máy tính và điện thoại", async () => {
    const calls: unknown[] = [];
    setApiTransport(async (path, init) => {
      calls.push({ path, method: init?.method, body: init?.body });
      return { playlist: (init?.body as { playlist: string | null }).playlist ?? undefined };
    });
    expect(await savePlaylistChoice("abc", "calm")).toEqual({ playlist: "calm" });
    await savePlaylistChoice("abc", null); // để máy chọn: server xoá khoá
    await savePlaylistChoice("abc", OFF_PLAYLIST); // tắt: server lưu "off"
    expect(calls).toEqual([
      { path: "/api/books/abc/music", method: "PUT", body: { playlist: "calm" } },
      { path: "/api/books/abc/music", method: "PUT", body: { playlist: null } },
      { path: "/api/books/abc/music", method: "PUT", body: { playlist: "off" } },
    ]);
  });
});

describe("tắt tự chọn nhạc nền trong Cài đặt", () => {
  it("cuốn chưa chọn nhạc nói đúng là chưa có nhạc, và dòng 'Để máy chọn' nói lý do", () => {
    const view = { autoOff: true };
    expect(playlistLabel(view, undefined)).toBe("Chưa có nhạc (tắt trong Cài đặt)");
    expect(playlistPlaying(view)).toBe(false);
    expect(chosenId(view)).toBeNull();
    expect(playlistOptions(undefined, false, view)[0]).toMatchObject({ id: null, hint: "đang tắt trong Cài đặt" });
  });

  it("danh mục chưa tải: không nói mã trần của danh sách đã chọn", () => {
    expect(playlistLabel({ playlist: "fantasy_adventure" }, undefined)).toBe("Danh sách đã chọn");
  });
});
