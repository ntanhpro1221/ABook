import { describe, expect, it } from "vitest";
import { analysisLabel, importSummary, isLocal, localDigest, mergeImports, previewPath, type ImportResult, type LocalTrack } from "./musicLocal";

const digest = "0123456789abcdef0123456789abcdef01234567";
const track = (over: Partial<LocalTrack> = {}): LocalTrack => ({
  link: `local:${digest}`, title: "Đêm trăng", creator: "Ai đó", duration: 200, analysed: false, name: "dem.mp3", bytes: 1, ...over,
});
const result = (over: Partial<ImportResult> = {}): ImportResult => ({ tracks: [], analyzer: false, added: [], existing: [], failed: [], ...over });

describe("local music links", () => {
  it("tells my tracks from catalog links and reads the content hash", () => {
    expect(isLocal(`local:${digest}`)).toBe(true);
    expect(isLocal("https://incompetech.com/a.mp3")).toBe(false);
    expect(localDigest(`local:${digest}`)).toBe(digest);
    expect(localDigest("local:xyz")).toBeNull();
    expect(localDigest("https://x/a.mp3")).toBeNull();
  });

  it("previews my tracks from the machine's own store and catalog tracks through the catalog route", () => {
    expect(previewPath(`local:${digest}`)).toBe(`/api/music/local/${digest}/file`);
    expect(previewPath("https://x/a b.mp3")).toBe("/api/music/track?link=https%3A%2F%2Fx%2Fa%20b.mp3");
  });
});

describe("analysis label", () => {
  it("says what the user can do with an unanalysed track instead of hiding it", () => {
    expect(analysisLabel({ analysed: false })).toContain("bạn vẫn ghim được");
    expect(analysisLabel({ analysed: true })).toContain("máy có thể tự chọn");
  });
});

describe("import summary", () => {
  it("counts new and already-present tracks and warns about the ones that could not be imported", () => {
    const summary = importSummary({ added: [track(), track({ analysed: true })], existing: [track()], failed: ["“x.txt”: định dạng lạ."] });
    expect(summary.kind).toBe("warning");
    expect(summary.title).toBe("Đã nhập: 2 bài mới, 1 bài đã có sẵn từ trước");
    expect(summary.description).toContain("x.txt");
    expect(summary.description).toContain("1 bài chưa phân tích");
  });

  it("is plain success when everything went in, and an error when nothing did", () => {
    expect(importSummary({ added: [track({ analysed: true })], existing: [], failed: [] })).toEqual({
      kind: "success", title: "Đã nhập: 1 bài mới", description: undefined,
    });
    const none = importSummary({ added: [], existing: [], failed: ["a", "b"] });
    expect(none.kind).toBe("error");
    expect(none.title).toBe("Không nhập được file nào");
    expect(none.description).toBe("a\nb");
  });

  it("merges the per-file results of one import and keeps the last track list", () => {
    const merged = mergeImports([result({ added: [track()], tracks: [track()] }), result({ failed: ["lỗi"], tracks: [track(), track({ title: "B" })] })]);
    expect(merged.added).toHaveLength(1);
    expect(merged.failed).toEqual(["lỗi"]);
    expect(merged.tracks).toHaveLength(2);
    expect(mergeImports([]).tracks).toEqual([]);
  });
});
