// @vitest-environment node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { filtering, libraryQuery, loadOf, NO_FILTERS, type LibraryFilters } from "./library";
import { previewVolume, PREVIEW_LUFS } from "./preview";
import { energyPercent, percent } from "./TrackSheet";

// Bảng ca chung của Kho nhạc (máy chủ / Android / Qt): web lọc ở máy chủ, nên ở đây kiểm mọi bộ lọc của bảng đi qua chuỗi truy vấn nguyên vẹn -
// máy chủ nhận đúng bộ lọc mà test_music_library.py đã kiểm kết quả.
const cases = JSON.parse(readFileSync(fileURLToPath(new URL("../../../tests/fixtures/music_library/cases.json", import.meta.url)), "utf8")) as {
  cases: { name: string; filter: Partial<LibraryFilters> }[];
};

function parsed(query: string): Partial<LibraryFilters> {
  const params = new URLSearchParams(query.replace(/^\?/, ""));
  const out: Partial<LibraryFilters> = {};
  for (const key of ["q", "playlist", "style", "emotion", "tempo", "length"] as const) {
    const value = params.get(key);
    if (value !== null) (out as Record<string, string>)[key] = value;
  }
  if (params.get("downloaded") === "1") out.downloaded = true;
  return out;
}

describe("Kho nhạc: chuỗi truy vấn", () => {
  it.each(cases.cases)("$name", ({ filter }) => {
    const sent = parsed(libraryQuery({ ...NO_FILTERS, ...filter }));
    const expected = Object.fromEntries(Object.entries(filter).filter(([, value]) => value !== "" && value !== false).map(([key, value]) => [key, typeof value === "string" ? value.trim() : value]));
    expect(sent).toEqual(expected);
  });

  it("không lọc gì thì không có chuỗi truy vấn; chữ tìm không tính là đang lọc", () => {
    expect(libraryQuery(NO_FILTERS)).toBe("");
    expect(filtering({ ...NO_FILTERS, q: "mưa" })).toBe(false);
    expect(filtering({ ...NO_FILTERS, tempo: "slow" })).toBe(true);
  });
});

describe("Kho nhạc: trạng thái tải, phần trăm, nghe thử", () => {
  const track = { link: "https://a", downloaded: false };
  it("đang tải hiện phần trăm (chưa biết cỡ: vòng quay), hỏng, đã tải, chưa tải", () => {
    expect(loadOf(track, { active: { "https://a": { done: 50, total: 200 } }, failed: {} })).toEqual({ kind: "loading", percent: 25 });
    expect(loadOf(track, { active: { "https://a": { done: 199, total: 200 } }, failed: {} })).toEqual({ kind: "loading", percent: 99 });
    expect(loadOf(track, { active: { "https://a": { done: 5, total: null } }, failed: {} })).toEqual({ kind: "loading", percent: null });
    expect(loadOf(track, { active: {}, failed: { "https://a": "mất mạng" } })).toEqual({ kind: "failed" });
    expect(loadOf({ ...track, downloaded: true }, undefined)).toEqual({ kind: "done" });
    expect(loadOf(track, undefined)).toEqual({ kind: "none" });
  });

  it("năng lượng -1..1 thành 0-100 %, điểm cảm xúc thành phần trăm", () => {
    expect(energyPercent(-1)).toBe(0);
    expect(energyPercent(0)).toBe(50);
    expect(energyPercent(0.582)).toBe(79);
    expect(energyPercent(undefined)).toBeNull();
    expect(percent(0.946)).toBe(95);
    expect(percent(1.2)).toBe(100);
  });

  it("nghe thử đưa bài về một mức to", () => {
    expect(previewVolume(PREVIEW_LUFS)).toBe(1);
    expect(previewVolume(PREVIEW_LUFS + 6)).toBeCloseTo(0.501, 3);
    expect(previewVolume(-30)).toBe(1); // bài nhỏ: không khuếch đại quá 1
    expect(previewVolume(undefined)).toBe(1);
  });
});
