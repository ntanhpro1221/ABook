import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { setApiTransport } from "./api";
import {
  cancelMusicReader,
  hasNativeMusicImport,
  importMusic,
  readerLabel,
  readerPercent,
  retryMusicReader,
  setNativeMusicImport,
  setReaderPollInterval,
} from "./musicImport";
import type { ImportResult, LocalMusicView, LocalTrack, MusicReader } from "./musicLocal";

const track = (name: string): LocalTrack => ({
  link: `local:${"0123456789abcdef0123456789abcdef01234567".slice(0, 39)}${name.length % 10}`,
  title: name,
  creator: "",
  duration: 60,
  analysed: false,
  name,
  bytes: 1,
});
const answer = (added: LocalTrack[], failed: string[] = []): ImportResult => ({ tracks: added, analyzer: false, added, existing: [], failed });

afterEach(() => {
  setApiTransport(null);
  setNativeMusicImport(null);
});

describe("nhập nhạc của tôi trên máy tính", () => {
  it("chọn file rồi nhập từng file một, báo tiến độ và gộp kết quả", async () => {
    const calls: string[] = [];
    setApiTransport(async (path, init) => {
      calls.push(`${init?.method ?? "GET"} ${path}`);
      if (path === "/api/dialog/files") return { paths: ["C:/a.mp3", "C:/b.wav"] };
      const body = init?.body as { paths: string[] };
      return answer([track(body.paths[0])]);
    });
    const progress: [number, number, boolean][] = [];
    const { result, error } = await importMusic((done, total, latest) => progress.push([done, total, latest !== undefined]));
    expect(error).toBeUndefined();
    expect(calls).toEqual(["POST /api/dialog/files", "POST /api/music/local/import", "POST /api/music/local/import"]);
    expect(progress).toEqual([
      [0, 2, false],
      [1, 2, true],
      [2, 2, true],
    ]);
    expect(result?.added.map((item) => item.title)).toEqual(["C:/a.mp3", "C:/b.wav"]);
  });

  it("không chọn file nào thì không có kết quả", async () => {
    setApiTransport(async () => ({ paths: [] }));
    expect(await importMusic(() => undefined)).toEqual({ result: null });
  });

  it("một lượt dừng giữa chừng vẫn trả phần đã nhập được", async () => {
    let imports = 0;
    setApiTransport(async (path, init) => {
      if (path === "/api/dialog/files") return { paths: ["a.mp3", "b.mp3"] };
      if (++imports === 2) throw new Error("mất kết nối");
      return answer([track((init?.body as { paths: string[] }).paths[0])]);
    });
    const { result, error } = await importMusic(() => undefined);
    expect(error?.message).toBe("mất kết nối");
    expect(result?.added).toHaveLength(1);
  });

  it("lỗi mở hộp chọn file thì ném cho nơi gọi báo", async () => {
    setApiTransport(async () => {
      throw new Error("Không mở được hộp chọn file");
    });
    await expect(importMusic(() => undefined)).rejects.toThrow("Không mở được hộp chọn file");
  });
});

describe("nhập nhạc của tôi trên điện thoại", () => {
  it("dùng lõi native đã đăng ký, không hỏi máy chủ", async () => {
    expect(hasNativeMusicImport()).toBe(false);
    setApiTransport(async () => {
      throw new Error("điện thoại không được gọi hộp chọn file của máy chủ");
    });
    setNativeMusicImport(async (progress) => {
      progress(1, 2);
      progress(2, 2, answer([track("x.mp3")]));
      return answer([track("x.mp3")]);
    });
    expect(hasNativeMusicImport()).toBe(true);
    const seen: number[] = [];
    const outcome = await importMusic((done) => seen.push(done));
    expect(seen).toEqual([1, 2]);
    expect(outcome.result?.added).toHaveLength(1);
  });

  it("lõi native báo lỗi hay không chọn file thì trả đúng như vậy", async () => {
    setNativeMusicImport(async () => null);
    expect(await importMusic(() => undefined)).toEqual({ result: null });
    setNativeMusicImport(async () => {
      throw new Error("không nhập được nhạc");
    });
    const { result, error } = await importMusic(() => undefined);
    expect(result).toBeNull();
    expect(error?.message).toBe("không nhập được nhạc");
  });
});

const reader = (patch: Partial<MusicReader> = {}): MusicReader => ({ state: "downloading", done: 0, total: 100, error: "", ready: false, ...patch });
const waiting = (value: MusicReader): ImportResult => ({ ...answer([]), needsReader: true, reader: value });
const view = (value: MusicReader): LocalMusicView => ({ tracks: [], analyzer: false, reader: value });
const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

describe("bộ đọc nhạc tải ở lần nhập đầu", () => {
  beforeEach(() => setReaderPollInterval(1));
  afterEach(() => setReaderPollInterval(1000));

  it("đợi tải xong rồi gửi lại đúng file ấy, báo phần trăm", async () => {
    const calls: string[] = [];
    const imports: string[] = [];
    let polls = 0;
    setApiTransport(async (path, init) => {
      calls.push(`${init?.method ?? "GET"} ${path}`);
      if (path === "/api/dialog/files") return { paths: ["C:/a.mp3"] };
      if (path === "/api/music/local") return view(++polls < 2 ? reader({ done: 40 }) : reader({ state: "ready", done: 100, ready: true }));
      imports.push((init?.body as { paths: string[] }).paths[0]);
      return imports.length === 1 ? waiting(reader({ done: 10 })) : answer([track("a.mp3")]);
    });
    const seen: (number | null)[] = [];
    const { result, error } = await importMusic(() => undefined, (value) => seen.push(value ? readerPercent(value) : null));
    expect(error).toBeUndefined();
    expect(imports).toEqual(["C:/a.mp3", "C:/a.mp3"]);
    expect(calls.filter((call) => call === "GET /api/music/local")).toHaveLength(2);
    expect(seen).toEqual([10, 40, null]);
    expect(result?.added).toHaveLength(1);
  });

  it("tải hỏng thì nói lý do; Thử lại gọi POST .../reader rồi đợi tiếp và nhập", async () => {
    const calls: string[] = [];
    let imports = 0;
    setApiTransport(async (path, init) => {
      calls.push(`${init?.method ?? "GET"} ${path}`);
      if (path === "/api/dialog/files") return { paths: ["a.mp3"] };
      if (path === "/api/music/local/reader") return view(reader({ done: 5 }));
      if (path === "/api/music/local") return view(reader({ state: "ready", done: 100, ready: true }));
      return ++imports === 1 ? waiting(reader({ state: "error", error: "không tải được - kiểm tra kết nối mạng" })) : answer([track("a.mp3")]);
    });
    const notices: (MusicReader | null)[] = [];
    const done = importMusic(() => undefined, (value) => notices.push(value));
    await tick();
    expect(readerLabel(notices[0]!)).toBe("Không tải được bộ đọc nhạc: không tải được - kiểm tra kết nối mạng");
    expect(calls).not.toContain("POST /api/music/local/reader");
    retryMusicReader();
    const { result, error } = await done;
    expect(error).toBeUndefined();
    expect(calls).toContain("POST /api/music/local/reader");
    expect(result?.added).toHaveLength(1);
    expect(notices.at(-1)).toBeNull();
  });

  it("Bỏ qua khi tải hỏng thì dừng, giữ phần đã nhập và nói lý do", async () => {
    let imports = 0;
    setApiTransport(async (path) => {
      if (path === "/api/dialog/files") return { paths: ["a.mp3", "b.mp3"] };
      return ++imports === 1 ? answer([track("a.mp3")]) : waiting(reader({ state: "error", error: "không ghi được vào ổ đĩa" }));
    });
    const done = importMusic(() => undefined);
    await tick();
    cancelMusicReader();
    const { result, error } = await done;
    expect(error?.message).toBe("Không tải được bộ đọc nhạc: không ghi được vào ổ đĩa");
    expect(result?.added).toHaveLength(1);
  });

  it("câu báo nói điều người nghe thấy", () => {
    expect(readerLabel(reader({ done: 31_246_824 / 2, total: 31_246_824 }))).toBe("Đang tải bộ đọc nhạc (~30 MB, một lần) 50%");
    expect(readerPercent(reader({ done: 5, total: 0 }))).toBe(0);
  });
});
