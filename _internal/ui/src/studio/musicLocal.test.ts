import { describe, expect, it } from "vitest";
import {
  analysisLabel, formatSize, importSummary, isLocal, localDigest, mergeImports, moduleLabel, modulePercent, preciseBusy, preciseLabel, preciseOffered, previewPath,
  type ImportResult, type LocalTrack, type MusicModuleStatus, type PreciseMood,
} from "./musicLocal";

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

describe("mô-đun Phân tích nhạc", () => {
  const status = (over: Partial<MusicModuleStatus> = {}): MusicModuleStatus => ({
    state: "missing", done: 0, total: 92_000_000, error: "", ready: false, analysing: false, metered: false, ...over,
  });
  it("nói MỘT tổng dung lượng trước khi bấm và phần trăm khi tải", () => {
    expect(moduleLabel(status())).toContain(formatSize(92_000_000));
    expect(moduleLabel(status())).toContain("vẫn nhập, nghe và ghim tay được");
    expect(moduleLabel(status({ state: "downloading", done: 30, total: 60 }))).toContain("50%");
    expect(modulePercent(status({ done: 5, total: 0 }))).toBe(0);
    expect(modulePercent(status({ done: 99, total: 60 }))).toBe(100);
  });
  it("nói lý do hỏng, việc đang làm và máy không tải được", () => {
    expect(moduleLabel(status({ state: "error", error: "Không tải được" }))).toBe("Không tải được");
    expect(moduleLabel(status({ state: "ready", ready: true, analysing: true }))).toContain("Đang nghe");
    expect(moduleLabel(status({ state: "unsupported", reason: "chỉ có cho Windows 64-bit" }))).toContain("Windows 64-bit");
  });
  it("có bản mới thì nói dung lượng phần phải tải, không phải cả mô-đun", () => {
    const outdated = status({ state: "outdated", ready: true, outdatedParts: ["Model nghe nhạc"], outdatedBytes: 59_000_000 });
    expect(moduleLabel(outdated)).toContain(`có bản mới - ${formatSize(59_000_000)}`);
    expect(moduleLabel(outdated)).not.toContain(formatSize(92_000_000));
  });
  it("sau khi cập nhật chỉ đề nghị phân tích lại, không tự làm; yên thì không nói gì", () => {
    expect(moduleLabel(status({ state: "ready", ready: true, stale: 3 }))).toContain("3 bài được phân tích bằng bản cũ");
    expect(moduleLabel(status({ state: "ready", ready: true }))).toBe("");
    expect(moduleLabel(status({ state: "ready", ready: true, restart: true }))).toContain("mở lại ABook");
  });
  it("dung lượng dễ đọc", () => {
    expect(formatSize(512)).toBe("1 KB");
    expect(formatSize(5.5 * 1024 * 1024)).toBe("5,5 MB");
    expect(formatSize(59_000_000)).toBe("56 MB");
    expect(formatSize(1_273_217_311)).toBe("1,27 GB");
  });
});

describe("đo cảm xúc nhạc chính xác hơn", () => {
  const precise = (over: Partial<PreciseMood> = {}): PreciseMood => ({
    state: "off", enabled: false, present: false, removable: false, reason: "", bytes: 1_273_217_311, done: 0, total: 0, error: "", working: false, pending: 0, ...over,
  });
  const module = (over: Partial<MusicModuleStatus> = {}): MusicModuleStatus => ({
    state: "ready", done: 0, total: 0, error: "", ready: true, analysing: false, metered: false, precise: precise(), ...over,
  });
  it("chỉ mời khi máy đủ sức và đã có bộ phân tích nhạc (điện thoại không có tuỳ chọn này)", () => {
    expect(preciseOffered(module())).toBe(true);
    expect(preciseOffered(module({ precise: precise({ state: "unavailable", reason: "cần máy có từ 8 GB RAM" }) }))).toBe(false);
    expect(preciseOffered(module({ ready: false }))).toBe(false);
    expect(preciseOffered(module({ precise: undefined }))).toBe(false);
    expect(preciseOffered(undefined)).toBe(false);
  });
  it("nói dung lượng phải tải trước khi bật, và không nhắc tải nếu file đã có", () => {
    expect(preciseLabel(precise())).toContain("Tải thêm 1,27 GB một lần");
    expect(preciseLabel(precise({ present: true }))).not.toContain("Tải thêm");
  });
  it("nói phần trăm khi tải, việc đang làm khi nghe kỹ lại, và lý do khi hỏng", () => {
    expect(preciseLabel(precise({ state: "downloading", done: 50, total: 100 }))).toContain("50%");
    expect(preciseLabel(precise({ state: "ready", enabled: true, present: true, working: true, pending: 4 }))).toContain("4 bài");
    expect(preciseLabel(precise({ state: "ready", enabled: true, present: true }))).toContain("Đang bật");
    expect(preciseLabel(precise({ state: "error", error: "Không tải được" }))).toBe("Không tải được");
    expect(preciseLabel(precise({ state: "missing", enabled: true }))).toContain("chưa tải xong");
  });
  it("hỏi lại view mỗi giây khi tải hoặc đang đo", () => {
    expect(preciseBusy(precise({ state: "downloading" }))).toBe(true);
    expect(preciseBusy(precise({ state: "ready", working: true }))).toBe(true);
    expect(preciseBusy(precise({ state: "ready" }))).toBe(false);
    expect(preciseBusy(undefined)).toBe(false);
  });
});
