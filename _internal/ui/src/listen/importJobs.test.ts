import { describe, expect, it } from "vitest";
import { endedSince, endedText, type ImportJob, type ImportJobsView } from "./importJobs";

const job = (id: string, state: ImportJob["state"], extra: Partial<ImportJob> = {}): ImportJob =>
  ({ id, kind: "book", name: "Sách thử", state, problem: "", result: null, ...extra });
const view = (revision: number, ...jobs: ImportJob[]): ImportJobsView => ({ revision, jobs });

describe("người xem cấp app của lượt thêm sách", () => {
  it("lần hỏi đầu là sổ cũ, không báo gì", () => {
    expect(endedSince(undefined, view(3, job("a", "done"), job("b", "failed")))).toEqual([]);
  });

  it("lượt đang chạy rồi xong / lỗi là tin mới; lượt đã xong từ trước thì không", () => {
    const before = view(1, job("a", "running"), job("b", "running"), job("c", "done"));
    const after = view(4, job("a", "done", { result: { id: "x", how: "new" } }), job("b", "failed", { problem: "Đây không phải file sách của app." }), job("c", "done"));
    expect(endedSince(before, after).map((row) => row.id)).toEqual(["a", "b"]);
  });

  it("lượt chạy và xong giữa hai nhịp hỏi (hộp đã đóng) vẫn được thấy", () => {
    expect(endedSince(view(1), view(3, job("z", "done"))).map((row) => row.id)).toEqual(["z"]);
  });

  it("chữ báo cùng chữ với thông báo của điện thoại", () => {
    expect(endedText(job("a", "done", { result: { how: "new" } }))).toEqual({ ok: true, text: "Đã thêm “Sách thử”" });
    expect(endedText(job("a", "done", { result: { how: "updated" } })).text).toBe("Đã cập nhật “Sách thử”");
    expect(endedText(job("a", "failed", { problem: "Đây không phải file sách của app." })))
      .toEqual({ ok: false, text: "Chưa thêm được sách", note: "Đây không phải file sách của app." });
    expect(endedText(job("a", "interrupted")).note).toBe("App đóng giữa lúc thêm, sách chưa vào thư viện.");
  });
});
