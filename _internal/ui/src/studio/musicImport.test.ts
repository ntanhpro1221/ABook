import { afterEach, describe, expect, it } from "vitest";
import { setApiTransport } from "./api";
import { hasNativeMusicImport, importMusic, setNativeMusicImport } from "./musicImport";
import type { ImportResult, LocalTrack } from "./musicLocal";

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
